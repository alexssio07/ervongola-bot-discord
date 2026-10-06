import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Grid,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiErrorMessage } from "../../api/client";
import { createMovie, getMovie, updateMovie, type MovieInput, type MovieStatus } from "../../api/movies";

const EMPTY_FORM: MovieInput = {
  title: "",
  link: "",
  platform: "",
  status: "da_guardare",
  cover_url: "",
  genre: "",
  notes: "",
};

export default function MovieFormPage() {
  const params = useParams<{ id: string }>();
  const isEditing = params.id !== undefined && params.id !== "new";
  const navigate = useNavigate();

  const [form, setForm] = useState<MovieInput>(EMPTY_FORM);
  const [loading, setLoading] = useState(isEditing);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isEditing) return;
    const id = Number(params.id);
    setLoading(true);
    getMovie(id)
      .then((movie) => {
        setForm({
          title: movie.title,
          link: movie.link,
          platform: movie.platform,
          status: movie.status,
          cover_url: movie.cover_url,
          genre: movie.genre,
          notes: movie.notes,
        });
      })
      .catch((err) => setError(apiErrorMessage(err, "Impossibile caricare il film.")))
      .finally(() => setLoading(false));
  }, [isEditing, params.id]);

  function setField<K extends keyof MovieInput>(field: K, value: MovieInput[K]) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!form.title?.trim()) {
      setError("Il titolo è obbligatorio.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (isEditing) {
        await updateMovie(Number(params.id), form);
      } else {
        await createMovie(form);
      }
      navigate("/movies");
    } catch (err) {
      setError(apiErrorMessage(err, "Errore durante il salvataggio."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" py={6}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box maxWidth={720} mx="auto">
      <Typography variant="h5" component="h1" gutterBottom>
        {isEditing ? "Modifica film" : "Aggiungi film"}
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper component="form" onSubmit={handleSubmit} variant="outlined" sx={{ p: 3 }}>
        <Grid container spacing={2}>
          <Grid size={12}>
            <TextField
              label="Titolo"
              value={form.title}
              onChange={(e) => setField("title", e.target.value)}
              required
              fullWidth
              autoFocus
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Link dove guardarlo"
              value={form.link}
              onChange={(e) => setField("link", e.target.value)}
              fullWidth
              placeholder="https://..."
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Piattaforma"
              value={form.platform}
              onChange={(e) => setField("platform", e.target.value)}
              fullWidth
              placeholder="Netflix, Prime Video, ..."
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              select
              label="Stato"
              value={form.status}
              onChange={(e) => setField("status", e.target.value as MovieStatus)}
              fullWidth
            >
              <MenuItem value="da_guardare">Da guardare</MenuItem>
              <MenuItem value="visto">Visto</MenuItem>
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              label="Genere"
              value={form.genre}
              onChange={(e) => setField("genre", e.target.value)}
              fullWidth
            />
          </Grid>
          <Grid size={12}>
            <TextField
              label="Link copertina"
              value={form.cover_url}
              onChange={(e) => setField("cover_url", e.target.value)}
              fullWidth
              placeholder="https://..."
            />
          </Grid>
          <Grid size={12}>
            <TextField
              label="Note"
              value={form.notes}
              onChange={(e) => setField("notes", e.target.value)}
              fullWidth
              multiline
              minRows={2}
            />
          </Grid>
        </Grid>

        <Stack direction="row" spacing={2} justifyContent="flex-end" mt={3}>
          <Button onClick={() => navigate("/movies")} disabled={saving}>
            Annulla
          </Button>
          <Button type="submit" variant="contained" disabled={saving}>
            {saving ? "Salvataggio..." : "Salva"}
          </Button>
        </Stack>
      </Paper>
    </Box>
  );
}
