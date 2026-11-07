# Security policy

## Supported versions

| Version | Supported |
| - | - |
| 2.1.x | yes |
| < 2.1 | no |

## Reporting a vulnerability

Please report security issues privately through GitHub Security Advisories:

- <https://github.com/Golybou/Tesseract_OCR_Studio/security/advisories/new>

Do not open a public issue for a vulnerability. Include a description, the affected
version, and the steps needed to reproduce the problem.

You can expect an acknowledgement within a few days. Fixes are published as a new
release together with an entry in `CHANGELOG.md`.

## Scope notes

Tesseract OCR Studio is a local desktop application. It does not send any data to
a remote server. Image data, OCR results and logs stay on the machine where the
application runs.

The application reads and writes:

- profiles in the `configs/` directory (or the directory set through
  `TESSERACT_STUDIO_CONFIG_DIR`);
- application settings in the `QSettings` location (or the file set through
  `TESSERACT_STUDIO_SETTINGS`);
- images that the user opens explicitly or captures from the screen.

No credentials, API keys or tokens are required or stored by the application.

The application starts the Tesseract OCR executable locally to recognise text.
That executable is installed separately by the user and is not part of this
repository.
