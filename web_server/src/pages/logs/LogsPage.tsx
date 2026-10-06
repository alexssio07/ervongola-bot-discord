import ClearIcon from "@mui/icons-material/Clear";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import {
  Box,
  Chip,
  FormControlLabel,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
  type SelectChangeEvent,
} from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";
import { logsStreamUrl } from "../../api/client";

interface LogLine {
  id: number;
  timestamp: string;
  level: string;
  logger: string;
  message: string;
}

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;
type Level = (typeof LEVELS)[number];

// Limite alla dimensione del buffer in memoria: un bot che gira per giorni
// può generare moltissime righe, e senza un tetto la pagina Log accumulerebbe
// log all'infinito (memory leak lato browser). Le righe più vecchie vengono
// scartate quando si supera il limite.
const MAX_LOGS = 500;

const LEVEL_COLOR: Record<Level, "default" | "info" | "warning" | "error"> = {
  DEBUG: "default",
  INFO: "info",
  WARNING: "warning",
  ERROR: "error",
  CRITICAL: "error",
};

type ConnectionState = "connecting" | "live" | "error";

let nextId = 0;

export default function LogsPage() {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [paused, setPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [levelFilter, setLevelFilter] = useState<Level[]>([...LEVELS]);
  const [textFilter, setTextFilter] = useState("");
  const [connection, setConnection] = useState<ConnectionState>("connecting");

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    const source = new EventSource(logsStreamUrl());

    source.onopen = () => setConnection("live");
    source.onerror = () => setConnection("error"); // EventSource riprova la connessione da solo

    source.onmessage = (event) => {
      if (pausedRef.current) return;
      try {
        const data = JSON.parse(event.data) as Omit<LogLine, "id">;
        setLogs((prev) => {
          const next = [...prev, { ...data, id: nextId++ }];
          return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
        });
        setConnection("live");
      } catch {
        // riga non JSON: la ignoriamo invece di far esplodere il listener
      }
    };

    return () => source.close();
  }, []);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filteredLogs = useMemo(() => {
    const q = textFilter.trim().toLowerCase();
    return logs.filter((log) => {
      if (!levelFilter.includes(log.level as Level)) return false;
      if (q && !log.message.toLowerCase().includes(q) && !log.logger.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [logs, levelFilter, textFilter]);

  function handleLevelChange(e: SelectChangeEvent<Level[]>) {
    const value = e.target.value;
    setLevelFilter(typeof value === "string" ? (value.split(",") as Level[]) : value);
  }

  const connectionMeta: Record<ConnectionState, { label: string; color: string }> = {
    connecting: { label: "Connessione...", color: "warning.main" },
    live: { label: "Live", color: "success.main" },
    error: { label: "Riconnessione...", color: "error.main" },
  };

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2} flexWrap="wrap" gap={1}>
        <Typography variant="h5" component="h1">
          Log del bot in diretta
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <FiberManualRecordIcon sx={{ fontSize: 12, color: connectionMeta[connection].color }} />
          <Typography variant="body2" color="text.secondary">
            {connectionMeta[connection].label}
          </Typography>
        </Stack>
      </Stack>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} mb={2} alignItems={{ sm: "center" }}>
        <Select
          multiple
          value={levelFilter}
          onChange={handleLevelChange}
          size="small"
          sx={{ minWidth: 220 }}
          renderValue={(selected) => selected.join(", ")}
        >
          {LEVELS.map((level) => (
            <MenuItem key={level} value={level}>
              {level}
            </MenuItem>
          ))}
        </Select>

        <TextField
          label="Filtra per testo"
          value={textFilter}
          onChange={(e) => setTextFilter(e.target.value)}
          size="small"
          fullWidth
        />

        <FormControlLabel
          control={<Switch checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />}
          label="Auto-scroll"
          sx={{ whiteSpace: "nowrap" }}
        />

        <Tooltip title={paused ? "Riprendi" : "Pausa"}>
          <IconButton onClick={() => setPaused((p) => !p)}>
            {paused ? <PlayArrowIcon /> : <PauseIcon />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Svuota">
          <IconButton onClick={() => setLogs([])}>
            <ClearIcon />
          </IconButton>
        </Tooltip>
      </Stack>

      <Paper
        variant="outlined"
        ref={scrollRef}
        sx={{
          flexGrow: 1,
          minHeight: 400,
          maxHeight: "65vh",
          overflowY: "auto",
          p: 1.5,
          fontFamily: "monospace",
          fontSize: "0.85rem",
          bgcolor: "background.default",
        }}
      >
        {filteredLogs.length === 0 ? (
          <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
            Nessuna riga di log da mostrare.
          </Typography>
        ) : (
          filteredLogs.map((log) => (
            <Box key={log.id} display="flex" gap={1} py={0.25} sx={{ wordBreak: "break-word" }}>
              <Typography component="span" color="text.secondary" sx={{ flexShrink: 0 }}>
                {log.timestamp}
              </Typography>
              <Chip
                label={log.level}
                size="small"
                color={LEVEL_COLOR[log.level as Level] ?? "default"}
                sx={{ height: 20, flexShrink: 0 }}
              />
              {log.logger && (
                <Typography component="span" color="text.secondary" sx={{ flexShrink: 0 }}>
                  [{log.logger}]
                </Typography>
              )}
              <Typography component="span">{log.message}</Typography>
            </Box>
          ))
        )}
      </Paper>
    </Box>
  );
}
