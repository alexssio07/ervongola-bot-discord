import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import SaveIcon from "@mui/icons-material/Save";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  MenuItem,
  Pagination,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { apiErrorMessage } from "../api/client";
import { addPhrase, deletePhrase, getPhrasePage, updatePhrase, type PhraseItem } from "../api/phrases";

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
const SEARCH_DEBOUNCE_MS = 300;

interface Props {
  fileKey: string;
}

/**
 * Editor generico per un file di frasi (frasiaddio / frasieffetto /
 * blasfemia): tabella compatta e paginata, ricerca "ogni parola" sopra la
 * tabella, sezione di inserimento in alto. Sostituisce sia la vecchia
 * ConfigEditorList (che caricava TUTTO il file in memoria e salvava con un
 * unico POST cumulativo) sia la logica duplicata di FrasiBenvenutoPage:
 * qui ogni azione (aggiungi/modifica/elimina) è una chiamata mirata al
 * backend, che scrive subito il JSON su disco.
 */
export default function PhraseEditor({ fileKey }: Props) {
  const [items, setItems] = useState<PhraseItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0]);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [newText, setNewText] = useState("");
  const [adding, setAdding] = useState(false);

  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);

  const [deletingIndex, setDeletingIndex] = useState<number | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Debounce della ricerca: evita una richiesta ad ogni tasto premuto.
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchInput]);

  // Reset quando si cambia file (cambio tab nella pagina "Modifica frasi").
  // pageSize NON viene resettato: è una preferenza dell'utente che ha senso
  // restare invariata passando da un tab all'altro.
  useEffect(() => {
    setSearchInput("");
    setSearch("");
    setPage(1);
    setEditingIndex(null);
    setError(null);
  }, [fileKey]);

  // Cambiare quanti elementi mostrare riparte sempre dalla prima pagina,
  // altrimenti si potrebbe restare su una pagina che non esiste più.
  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPhrasePage(fileKey, page, pageSize, search)
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(apiErrorMessage(err, "Errore nel caricamento delle frasi."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fileKey, page, pageSize, search]);

  // Se una modifica/eliminazione svuota l'ultima pagina, torna indietro.
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const data = await getPhrasePage(fileKey, page, pageSize, search);
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(apiErrorMessage(err, "Errore nel caricamento delle frasi."));
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd() {
    const text = newText.trim();
    if (!text) return;
    setAdding(true);
    setError(null);
    try {
      await addPhrase(fileKey, text);
      setNewText("");
      await reload();
    } catch (err) {
      setError(apiErrorMessage(err, "Errore durante l'inserimento."));
    } finally {
      setAdding(false);
    }
  }

  function startEdit(item: PhraseItem) {
    setEditingIndex(item.index);
    setEditingText(item.text);
  }

  function cancelEdit() {
    setEditingIndex(null);
    setEditingText("");
  }

  async function saveEdit(index: number) {
    const text = editingText.trim();
    if (!text) return;
    setSavingEdit(true);
    setError(null);
    try {
      await updatePhrase(fileKey, index, text);
      setEditingIndex(null);
      await reload();
    } catch (err) {
      setError(apiErrorMessage(err, "Errore durante il salvataggio."));
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleDelete(index: number) {
    setDeletingIndex(index);
    setError(null);
    try {
      await deletePhrase(fileKey, index);
      await reload();
    } catch (err) {
      setError(apiErrorMessage(err, "Errore durante l'eliminazione."));
    } finally {
      setDeletingIndex(null);
    }
  }

  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField
            label="Nuova frase"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
            }}
            fullWidth
            size="small"
          />
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAdd}
            disabled={adding || !newText.trim()}
          >
            Aggiungi
          </Button>
        </Stack>
      </Paper>

      <TextField
        label="Cerca (ogni parola, in qualsiasi ordine)"
        value={searchInput}
        onChange={(e) => setSearchInput(e.target.value)}
        fullWidth
        size="small"
        sx={{ mb: 2 }}
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell width={64}>#</TableCell>
              <TableCell>Testo</TableCell>
              <TableCell width={110} align="right">
                Azioni
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={3} align="center" sx={{ py: 4 }}>
                  <CircularProgress size={24} />
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    {search ? `Nessun risultato per "${search}".` : "Nessuna frase presente."}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.index} hover>
                  <TableCell>{item.index + 1}</TableCell>
                  <TableCell>
                    {editingIndex === item.index ? (
                      <TextField
                        value={editingText}
                        onChange={(e) => setEditingText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveEdit(item.index);
                          if (e.key === "Escape") cancelEdit();
                        }}
                        fullWidth
                        size="small"
                        variant="standard"
                        autoFocus
                      />
                    ) : (
                      item.text
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {editingIndex === item.index ? (
                      <>
                        <IconButton
                          size="small"
                          color="primary"
                          onClick={() => saveEdit(item.index)}
                          disabled={savingEdit || !editingText.trim()}
                          aria-label="Salva"
                        >
                          <SaveIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" onClick={cancelEdit} aria-label="Annulla">
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      </>
                    ) : (
                      <>
                        <IconButton size="small" onClick={() => startEdit(item)} aria-label="Modifica">
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDelete(item.index)}
                          disabled={deletingIndex === item.index}
                          aria-label="Elimina"
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        mt={2}
        flexWrap="wrap"
        gap={1}
      >
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="body2" color="text.secondary">
            {total} frasi{search ? " (filtrate)" : ""}
          </Typography>
          <TextField
            select
            label="Per pagina"
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            size="small"
            variant="standard"
            sx={{ minWidth: 90 }}
          >
            {PAGE_SIZE_OPTIONS.map((n) => (
              <MenuItem key={n} value={n}>
                {n}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
        {totalPages > 1 && (
          <Pagination
            count={totalPages}
            page={page}
            onChange={(_, value) => setPage(value)}
            color="primary"
            size="small"
          />
        )}
      </Stack>
    </Box>
  );
}
