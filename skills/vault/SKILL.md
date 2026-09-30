---
name: vault
description: Securely stores, retrieves, and manages long-term user preferences, profile keys, persistent memories, and sensitive configurations.
version: 1.0.0
permissions:
  - vault:read
  - vault:write
actions:
  - name: get_secret
    description: Retrieve a stored preference, configuration value, or profile variable by key
    required_inputs:
      - key
    output_format: json
  - name: set_secret
    description: Persist a key-value preference or profile setting into secure storage
    required_inputs:
      - key
      - value
    output_format: text
  - name: list_keys
    description: List stored profile setting keys without exposing sensitive values
    required_inputs: []
    output_format: json
---

# Vault Skill

The **Vault Skill** interfaces with the relational and encrypted storage layer to provide persistent profile memory and secure variable recall across sessions.
