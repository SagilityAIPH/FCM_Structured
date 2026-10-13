"""Reset a claimant's Subject Line Builder referral details in the UAT RRS database for retesting.

Runs [dbo].[sp_DeleteSubjectLineReferralDetails] @Claimant using FCM_RRS_DB_CONNECTION
(environment variable, or AI/.env).

    python Processes/SubjectLineBuilder/reset_test_claimant.py "ALEXANDRIA CORDOVA"
    python Processes/SubjectLineBuilder/reset_test_claimant.py          # prompts for the claimant
"""
import argparse
import os
import re
import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / 'AI' / '.env'


def connection_string():
    value = os.environ.get('FCM_RRS_DB_CONNECTION')
    if not value and ENV_FILE.exists():
        found = re.search(r'(?m)^\s*FCM_RRS_DB_CONNECTION\s*=\s*"?([^"\r\n]*)"?', ENV_FILE.read_text(encoding='utf8'))
        value = found.group(1) if found else ''
    if not value:
        sys.exit(f'FCM_RRS_DB_CONNECTION is not set (environment or {ENV_FILE}).')
    return value


def target(conn):
    parts = dict(p.split('=', 1) for p in conn.split(';') if '=' in p)
    parts = {k.strip().upper(): v.strip() for k, v in parts.items()}
    return parts.get('SERVER', '?'), parts.get('DATABASE', parts.get('INITIAL CATALOG', '?'))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('claimant', nargs='?', help='Claimant name as shown in RRS, e.g. "ALEXANDRIA CORDOVA"')
    parser.add_argument('-y', '--yes', action='store_true', help='Skip the confirmation prompt')
    args = parser.parse_args()
    claimant = (args.claimant or input('Claimant name: ')).strip()
    if not claimant:
        sys.exit('No claimant entered.')

    import pyodbc
    conn = connection_string()
    server, database = target(conn)
    if 'uat' not in server.lower():
        sys.exit(f'Refusing to run: {server} is not a UAT server.')
    print(f'Server: {server}  Database: {database}  Claimant: {claimant}')
    if not args.yes and input('Delete this claimant\'s subject line referral details? [y/N] ').strip().lower() != 'y':
        sys.exit('Cancelled.')

    with pyodbc.connect(conn, timeout=30) as db:
        cursor = db.cursor()
        cursor.execute('SET NOCOUNT OFF; EXEC [dbo].[sp_DeleteSubjectLineReferralDetails] @Claimant = ?', claimant)
        while True:
            if cursor.description:
                columns = [d[0] for d in cursor.description]
                for row in cursor.fetchall():
                    print(', '.join(f'{c}={v}' for c, v in zip(columns, row)))
            if not cursor.nextset():
                break
        db.commit()
    print('Done. Refresh RRS / reopen the Email Display to see the reset data.')


if __name__ == '__main__':
    main()
