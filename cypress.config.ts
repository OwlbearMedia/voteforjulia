import { readFileSync } from 'fs';
import { defineConfig } from 'cypress';
import { google } from 'googleapis';

type CypressEnv = Record<string, unknown>;

function getCredentials(env: CypressEnv): object {
  const json = env.GOOGLE_SERVICE_ACCOUNT_JSON ?? process.env.GOOGLE_SERVICE_ACCOUNT_JSON;
  if (json) {
    if (typeof json === 'object') return json;
    if (typeof json === 'string') return JSON.parse(json) as object;
  }

  const file =
    (env.GOOGLE_SERVICE_ACCOUNT_FILE as string | undefined) ??
    process.env.GOOGLE_SERVICE_ACCOUNT_FILE;
  if (file) return JSON.parse(readFileSync(file, 'utf8')) as object;

  throw new Error(
    'Google Sheets credentials not configured. ' +
      'Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE in cypress.env.json or as an env var.'
  );
}

function getSpreadsheetId(env: CypressEnv): string {
  const id = env.GOOGLE_SHEETS_SPREADSHEET_ID ?? process.env.GOOGLE_SHEETS_SPREADSHEET_ID;
  if (!id || typeof id !== 'string')
    throw new Error(
      'GOOGLE_SHEETS_SPREADSHEET_ID is not set in cypress.env.json or as an env var.'
    );
  return id;
}

function buildSheetsClient(env: CypressEnv) {
  const auth = new google.auth.GoogleAuth({
    credentials: getCredentials(env),
    scopes: ['https://www.googleapis.com/auth/spreadsheets']
  });
  return google.sheets({ version: 'v4', auth });
}

export default defineConfig({
  e2e: {
    // Default to the staging site. Override with CYPRESS_BASE_URL for local dev:
    //   CYPRESS_BASE_URL=http://localhost:5173 pnpm test:e2e
    baseUrl: 'https://test.voteforjulia.com',
    allowCypressEnv: false,
    defaultCommandTimeout: 10000,
    setupNodeEvents(on, config) {
      const env = config.env as CypressEnv;

      on('task', {
        async findSheetRow({ email }: { email: string }): Promise<{
          rowIndex: number;
          row: string[];
        } | null> {
          const spreadsheetId = getSpreadsheetId(env);
          const worksheet =
            (env.GOOGLE_SHEETS_WORKSHEET as string | undefined) ??
            process.env.GOOGLE_SHEETS_WORKSHEET;
          const sheets = buildSheetsClient(env);

          const response = await sheets.spreadsheets.values.get({
            spreadsheetId,
            range: worksheet ? `${worksheet}!A:G` : 'A:G'
          });

          const rows = response.data.values ?? [];
          // Column layout: [timestamp, firstName, lastName, email, phone, helpWays, message]
          const rowIndex = rows.findIndex((row) => row[3] === email);
          if (rowIndex < 0) return null;

          return { rowIndex, row: rows[rowIndex] as string[] };
        },

        async deleteSheetRow({ rowIndex }: { rowIndex: number }): Promise<true> {
          const spreadsheetId = getSpreadsheetId(env);
          const worksheet =
            (env.GOOGLE_SHEETS_WORKSHEET as string | undefined) ??
            process.env.GOOGLE_SHEETS_WORKSHEET;
          const sheets = buildSheetsClient(env);

          // Resolve the numeric sheetId for the named worksheet.
          const spreadsheet = await sheets.spreadsheets.get({ spreadsheetId });
          const sheet = spreadsheet.data.sheets?.find((s) => s.properties?.title === worksheet);
          const sheetId = sheet?.properties?.sheetId ?? 0;

          await sheets.spreadsheets.batchUpdate({
            spreadsheetId,
            requestBody: {
              requests: [
                {
                  deleteDimension: {
                    range: {
                      sheetId,
                      dimension: 'ROWS',
                      startIndex: rowIndex,
                      endIndex: rowIndex + 1
                    }
                  }
                }
              ]
            }
          });

          return true;
        }
      });
    }
  }
});
