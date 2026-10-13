# CMSCustomerSearch portable

Extract this ZIP into a writable folder. No Python or Node.js installation is
needed. Run `CMSCustomerSearch.exe`.

## Private configuration

Rename `.env.example` to `.env` beside the executable. Copy
`FCM_CMS_DB_CONNECTION` and `FCM_RRS_DB_CONNECTION` from your existing `AI\.env`
into that file. Fill in CMS credentials and optional sample input fields.
The **Load sample data** button fills the editable Live CMS form; it does not
start a run.

Alternatively, keep your existing `AI\.env` inside an `AI` subfolder beside the
executable. Settings are read from the executable's folder, not the working
directory or the temporary extraction folder. Existing Windows environment
variables take priority, then `.env`, then `AI\.env`, then
`Processes\Reopen-Check\Stand-Alone\.env`. Restart the app after changing settings.
`CMS_USER` and `CMS_PASSWORD` are also supported for sample credentials.

Never upload `.env`, credentials, connection strings, or live result files to
GitHub. The distributed template intentionally contains no credentials.
Optional machine settings belong in `config\local_settings.ini` beside the EXE.

## Machine requirements

- Windows x64 with Microsoft Edge WebView2 Runtime and .NET Framework 4.8.
- For live CMS: Microsoft Edge with IE mode enabled, the SQL Server ODBC driver
  named in your connection strings, and network/VPN access to CMS and databases.
- Selenium Manager may need internet access to obtain the matching Chromium
  Edge driver for CEM. The IE-mode driver is bundled.

The form scrolls independently above the Run/Save controls and output panel.
Progress appears during a run; the final JSON appears when the run finishes.
Offline scenarios do not contact CMS or the databases.
