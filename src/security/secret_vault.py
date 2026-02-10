"""
SOVRA Security - Secret Vault
Masks sensitive values (emails, API keys, passwords) before they reach the LLM.
Unmasks them before execution so real credentials are used.
"""

import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Default vault file path
DEFAULT_VAULT_PATH = os.path.join(
    os.path.expanduser("~"), ".sovra", "secrets.json"
)


class SecretVault:
    """
    Manages secrets that should never be exposed to the LLM.

    Usage:
        vault = SecretVault()
        vault.set("EMAIL", "real@gmail.com")

        # Before sending to LLM:
        masked = vault.mask("kirim email ke real@gmail.com")
        # → "kirim email ke [SECRET:EMAIL]"

        # Before executing command:
        unmasked = vault.unmask("kirim email ke [SECRET:EMAIL]")
        # → "kirim email ke real@gmail.com"
    """

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = vault_path or DEFAULT_VAULT_PATH
        self._secrets: dict[str, str] = {}
        self._load()

    def _load(self):
        """Load secrets from disk."""
        if os.path.exists(self.vault_path):
            try:
                with open(self.vault_path, "r") as f:
                    self._secrets = json.load(f)
                logger.info(f"🔐 Loaded {len(self._secrets)} secrets from vault")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load vault: {e}")
                self._secrets = {}
        else:
            self._secrets = {}

    def _save(self):
        """Save secrets to disk."""
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        with open(self.vault_path, "w") as f:
            json.dump(self._secrets, f, indent=2)
        logger.info(f"🔐 Saved {len(self._secrets)} secrets to vault")

    def set(self, name: str, value: str):
        """Store a secret."""
        name = name.upper().strip()
        self._secrets[name] = value
        self._save()
        logger.info(f"🔐 Secret '{name}' stored ({len(value)} chars)")

    def get(self, name: str) -> Optional[str]:
        """Retrieve a secret value."""
        return self._secrets.get(name.upper().strip())

    def delete(self, name: str) -> bool:
        """Delete a secret."""
        name = name.upper().strip()
        if name in self._secrets:
            del self._secrets[name]
            self._save()
            return True
        return False

    def list_names(self) -> list[str]:
        """List all secret names (not values)."""
        return list(self._secrets.keys())

    def mask(self, text: str) -> str:
        """
        Replace real secret values in text with [SECRET:NAME] placeholders.
        Called BEFORE sending text to LLM.
        """
        masked = text
        for name, value in self._secrets.items():
            if value and value in masked:
                masked = masked.replace(value, f"[SECRET:{name}]")
        return masked

    def unmask(self, text: str) -> str:
        """
        Replace [SECRET:NAME] placeholders with real values.
        Called BEFORE executing commands.
        """
        def replace_placeholder(match):
            name = match.group(1)
            real_value = self._secrets.get(name)
            if real_value:
                return real_value
            return match.group(0)  # Keep placeholder if not found

        pattern = r"\[SECRET:([A-Z_][A-Z0-9_]*)\]"
        return re.sub(pattern, replace_placeholder, text)

    def handle_command(self, command_text: str) -> str:
        """
        Handle /secret commands from users.
        /secret set NAME value
        /secret delete NAME
        /secret list
        """
        parts = command_text.strip().split(maxsplit=2)

        if len(parts) < 1:
            return "Usage: /secret set NAME value | /secret delete NAME | /secret list"

        action = parts[0].lower() if len(parts) >= 1 else ""

        if action == "list":
            names = self.list_names()
            if names:
                items = "\n".join([f"  🔑 {n}" for n in names])
                return f"Stored secrets:\n{items}"
            return "No secrets stored yet."

        elif action == "set" and len(parts) >= 3:
            name = parts[1]
            value = parts[2]
            self.set(name, value)
            masked_value = value[:3] + "***" + value[-2:] if len(value) > 5 else "***"
            return f"✅ Secret '{name.upper()}' stored: {masked_value}"

        elif action == "delete" and len(parts) >= 2:
            name = parts[1]
            if self.delete(name):
                return f"🗑️ Secret '{name.upper()}' deleted."
            return f"Secret '{name.upper()}' not found."

        else:
            return "Usage: /secret set NAME value | /secret delete NAME | /secret list"
