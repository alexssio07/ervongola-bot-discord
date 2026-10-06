import {
  Alert,
  Box,
  Button,
  Link,
  Paper,
  TextField,
  Typography,
} from "@mui/material";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

type Mode = "login" | "register";

export default function LoginPage() {
  const { isAuthenticated, login, register } = useAuth();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>("login");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) {
    const redirectTo = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={redirectTo} replace />;
  }

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setPassword("");
    setConfirmPassword("");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (mode === "register" && password !== confirmPassword) {
      setError("Le due password non coincidono.");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register(username, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Errore imprevisto.");
    } finally {
      setSubmitting(false);
    }
  }

  const isRegister = mode === "register";

  return (
    <Box
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      px={2}
    >
      <Paper component="form" onSubmit={handleSubmit} elevation={3} sx={{ p: 4, width: "100%", maxWidth: 380 }}>
        <Typography variant="h5" component="h1" gutterBottom>
          Er Vongola — Pannello
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={3}>
          {isRegister ? "Crea un nuovo account per accedere al pannello." : "Accedi con le tue credenziali."}
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <TextField
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          fullWidth
          required
          autoFocus
          margin="normal"
          autoComplete="username"
        />
        <TextField
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          fullWidth
          required
          margin="normal"
          autoComplete={isRegister ? "new-password" : "current-password"}
        />
        {isRegister && (
          <TextField
            label="Conferma password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            fullWidth
            required
            margin="normal"
            autoComplete="new-password"
          />
        )}

        <Button
          type="submit"
          variant="contained"
          fullWidth
          size="large"
          disabled={submitting}
          sx={{ mt: 2 }}
        >
          {submitting
            ? isRegister
              ? "Registrazione in corso..."
              : "Accesso in corso..."
            : isRegister
              ? "Registrati"
              : "Accedi"}
        </Button>

        <Typography variant="body2" align="center" sx={{ mt: 2 }}>
          {isRegister ? (
            <>
              Hai già un account?{" "}
              <Link component="button" type="button" onClick={() => switchMode("login")}>
                Accedi
              </Link>
            </>
          ) : (
            <>
              Non hai un account?{" "}
              <Link component="button" type="button" onClick={() => switchMode("register")}>
                Registrati
              </Link>
            </>
          )}
        </Typography>
      </Paper>
    </Box>
  );
}
