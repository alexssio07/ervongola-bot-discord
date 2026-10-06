import AddIcon from "@mui/icons-material/Add";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import MovieIcon from "@mui/icons-material/Movie";
import ScheduleIcon from "@mui/icons-material/Schedule";
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardMedia,
  Chip,
  CircularProgress,
  Grid,
  IconButton,
  MenuItem,
  Pagination,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { apiErrorMessage } from "../../api/client";
import { deleteMovie, listMovies, type Movie, type MovieStatus } from "../../api/movies";

const SEARCH_DEBOUNCE_MS = 300;
const PAGE_SIZE_OPTIONS = [12, 24, 48, 96];

const STATUS_META: Record<MovieStatus, { label: string; color: "success" | "warning"; icon: typeof CheckCircleIcon }> = {
  visto: { label: "Visto", color: "success", icon: CheckCircleIcon },
  da_guardare: { label: "Da guardare", color: "warning", icon: ScheduleIcon },
};

export default function MoviesListPage() {
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [status, setStatus] = useState<MovieStatus | "">("");
  const [platform, setPlatform] = useState("");
  const [genre, setGenre] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE_OPTIONS[0]);
  const [total, setTotal] = useState(0);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchInput]);

  // Ogni cambio di filtro o di quantità per pagina riparte dalla prima
  // pagina, altrimenti si potrebbe restare su una pagina che non esiste più
  // per i nuovi criteri (stesso pattern già usato in PhraseEditor).
  useEffect(() => {
    setPage(1);
  }, [status, platform, genre, search, pageSize]);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const data = await listMovies({ status, platform, genre, search }, page, pageSize);
      setMovies(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(apiErrorMessage(err, "Errore nel caricamento dei film."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, platform, genre, search, page, pageSize]);

  // Se un'eliminazione svuota l'ultima pagina, torna indietro (come in PhraseEditor).
  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  async function handleDelete(movie: Movie) {
    if (!window.confirm(`Eliminare "${movie.title}" dal catalogo?`)) return;
    setDeletingId(movie.id);
    setError(null);
    try {
      await deleteMovie(movie.id);
      // Ricarica invece di filtrare in locale: con la paginazione, il totale
      // e il conteggio pagine vanno ricalcolati dal backend (es. eliminando
      // l'ultimo film di una pagina bisogna sapere se quella pagina esiste
      // ancora).
      await reload();
    } catch (err) {
      setError(apiErrorMessage(err, "Errore durante l'eliminazione."));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h1">
          Film visti su Discord
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} component={RouterLink} to="/movies/new">
          Aggiungi film
        </Button>
      </Stack>

      <Grid container spacing={2} mb={3}>
        <Grid size={{ xs: 12, sm: 3 }}>
          <TextField
            select
            label="Stato"
            value={status}
            onChange={(e) => setStatus(e.target.value as MovieStatus | "")}
            fullWidth
            size="small"
          >
            <MenuItem value="">Tutti</MenuItem>
            <MenuItem value="visto">Visto</MenuItem>
            <MenuItem value="da_guardare">Da guardare</MenuItem>
          </TextField>
        </Grid>
        <Grid size={{ xs: 12, sm: 3 }}>
          <TextField
            label="Piattaforma"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            fullWidth
            size="small"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 3 }}>
          <TextField label="Genere" value={genre} onChange={(e) => setGenre(e.target.value)} fullWidth size="small" />
        </Grid>
        <Grid size={{ xs: 12, sm: 3 }}>
          <TextField
            label="Cerca titolo/note"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            fullWidth
            size="small"
          />
        </Grid>
      </Grid>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : movies.length === 0 ? (
        <Typography color="text.secondary" align="center" py={6}>
          Nessun film trovato con i filtri correnti.
        </Typography>
      ) : (
        <Grid container spacing={2}>
          {movies.map((movie) => {
            const meta = STATUS_META[movie.status];
            const StatusIcon = meta.icon;
            return (
              <Grid key={movie.id} size={{ xs: 12, sm: 6, md: 4, lg: 3 }}>
                <Card sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
                  {movie.cover_url ? (
                    <CardMedia
                      component="img"
                      image={movie.cover_url}
                      alt={`Copertina di ${movie.title}`}
                      sx={{ height: 200, objectFit: "cover" }}
                    />
                  ) : (
                    <Box
                      sx={{
                        height: 200,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        bgcolor: "action.hover",
                      }}
                    >
                      <MovieIcon sx={{ fontSize: 48, opacity: 0.4 }} />
                    </Box>
                  )}
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Typography variant="h6" component="h2" gutterBottom noWrap title={movie.title}>
                      {movie.title}
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mb={1}>
                      <Chip
                        size="small"
                        icon={<StatusIcon fontSize="small" />}
                        label={meta.label}
                        color={meta.color}
                        variant="filled"
                      />
                      {movie.platform && <Chip size="small" label={movie.platform} variant="outlined" />}
                      {movie.genre && <Chip size="small" label={movie.genre} variant="outlined" />}
                    </Stack>
                    {movie.notes && (
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        {movie.notes}
                      </Typography>
                    )}
                  </CardContent>
                  <CardActions sx={{ justifyContent: "space-between", px: 2, pb: 2 }}>
                    {movie.link ? (
                      <Button size="small" href={movie.link} target="_blank" rel="noopener noreferrer">
                        Guarda
                      </Button>
                    ) : (
                      <span />
                    )}
                    <Box>
                      <Tooltip title="Modifica">
                        <IconButton size="small" component={RouterLink} to={`/movies/${movie.id}`}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Elimina">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDelete(movie)}
                          disabled={deletingId === movie.id}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </CardActions>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        mt={3}
        flexWrap="wrap"
        gap={1}
      >
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="body2" color="text.secondary">
            {total} film{search ? " (filtrati)" : ""}
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
