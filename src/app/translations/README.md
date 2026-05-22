# Translations Directory

This directory contains translation files for the Korzen application.

## Structure

```
translations/
├── pl/                     # Polish translations (default)
│   └── LC_MESSAGES/
│       ├── messages.po     # Polish translation source (to be generated)
│       └── messages.mo     # Compiled Polish translations (to be generated)
└── en/                     # English translations
    └── LC_MESSAGES/
        ├── messages.po     # English translation source (to be generated)
        └── messages.mo     # Compiled English translations (to be generated)
```

## Workflow

### 1. Extract translatable strings from code

```bash
pybabel extract -F babel.cfg -k _l -o messages.pot .
```

This creates a `messages.pot` template file with all translatable strings.

### 2. Initialize new language (first time only)

```bash
# Polish
pybabel init -i messages.pot -d src/app/translations -l pl

# English
pybabel init -i messages.pot -d src/app/translations -l en
```

### 3. Update existing translations (after adding new strings)

```bash
pybabel update -i messages.pot -d src/app/translations
```

### 4. Edit translation files

Edit the `.po` files in each language directory:
- `src/app/translations/pl/LC_MESSAGES/messages.po`
- `src/app/translations/en/LC_MESSAGES/messages.po`

### 5. Compile translations for production

```bash
pybabel compile -d src/app/translations
```

This creates `.mo` files that Flask-Babel uses at runtime.

## Supported Languages

- **Polish (pl)** - Default language
- **English (en)** - Secondary language

## Notes

- The `.po` files are human-readable and should be edited by translators
- The `.mo` files are binary and generated automatically - do not edit manually
- Always compile translations before deploying to production
- The `messages.pot` template file can be regenerated at any time
