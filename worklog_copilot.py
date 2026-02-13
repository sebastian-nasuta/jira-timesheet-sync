#!/usr/bin/env python3

import sys, os, re, shutil, json, subprocess, argparse
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd

class Config:
    JIRA_BASE_URL = "https://jira.twoja-firma.com"
    JIRA_CREDENTIALS = ""
    INPUT_DIR, OUTPUT_DIR, SYNC_LOG_DIR = "in", "out", "sync_logs"
    TASK_COLUMN, COMMENT_COLUMN, TIME_COLUMN = "TASK", "COMMENT", "TIME"
    JIRA_KEY_PATTERN = r'\[([A-Z]+-\d+)\]'

class WorklogEntry:
    def __init__(self, task_key: str, comment: str, time_spent: str, row_index: int):
        self.task_key = task_key
        self.comment = comment
        self.time_spent = time_spent
        self.row_index = row_index
        self.is_synced = False

    def to_jira_format(self, worklog_date: str = None) -> Dict:
        date_obj = datetime.strptime(worklog_date, "%Y%m%d") if worklog_date else datetime.now()
        return {
            "comment": self.comment,
            "timeSpent": self.time_spent,
            "started": date_obj.strftime("%Y-%m-%dT15:00:00.000+0200")
        }

class SyncLogger:
    def __init__(self):
        os.makedirs(Config.SYNC_LOG_DIR, exist_ok=True)
        self._cache = {}

    def load_sync_log(self, date_str: str) -> Dict:
        if date_str in self._cache:
            return self._cache[date_str]
            
        log_path = os.path.join(Config.SYNC_LOG_DIR, f"{date_str}_sync.json")
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._cache[date_str] = data
                    return data
            except Exception as e:
                print(f"Cannot load sync log {log_path}: {e}")
        
        data = {"date": date_str, "synced_tasks": {}, "created": datetime.now().isoformat(), "last_updated": datetime.now().isoformat()}
        self._cache[date_str] = data
        return data

    def save_sync_log(self, date_str: str, sync_data: Dict):
        sync_data["last_updated"] = datetime.now().isoformat()
        self._cache[date_str] = sync_data
        try:
            with open(os.path.join(Config.SYNC_LOG_DIR, f"{date_str}_sync.json"), 'w', encoding='utf-8') as f:
                json.dump(sync_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving sync log: {e}")

    def mark_task_synced(self, date_str: str, worklog: WorklogEntry):
        sync_log = self.load_sync_log(date_str)
        sync_log["synced_tasks"][worklog.task_key] = {"row_index": worklog.row_index, "comment": worklog.comment, "time_spent": worklog.time_spent, "sync_timestamp": datetime.now().isoformat()}
        self.save_sync_log(date_str, sync_log)

    def is_task_synced(self, date_str: str, worklog: WorklogEntry) -> bool:
        return worklog.task_key in self.load_sync_log(date_str)["synced_tasks"]

class ExcelParser:
    @staticmethod
    def parse_file(file_path: str) -> Tuple[pd.DataFrame, List[WorklogEntry], int]:
        try:
            df = pd.read_excel(file_path)
            worklogs = []
            skipped_count = 0
            
            for idx, row in df.iterrows():
                result = ExcelParser._process_row(idx, row)
                if result['status'] == 'worklog':
                    worklogs.append(result['worklog'])
                elif result['status'] == 'skipped':
                    skipped_count += 1
            
            print(f"Found {len(worklogs)} worklogs")
            if skipped_count > 0:
                print(f"Skipped {skipped_count} tasks due to missing comments")
            return df, worklogs, skipped_count
        except Exception as e:
            print(f"Error parsing file {file_path}: {e}")
            raise

    @staticmethod
    def _process_row(idx: int, row) -> Dict:
        task = str(row[Config.TASK_COLUMN]) if pd.notna(row[Config.TASK_COLUMN]) else ''
        comment = str(row[Config.COMMENT_COLUMN]) if pd.notna(row[Config.COMMENT_COLUMN]) else ''
        time_spent = row[Config.TIME_COLUMN] if pd.notna(row[Config.TIME_COLUMN]) else None
        
        match = re.search(Config.JIRA_KEY_PATTERN, task)
        if not match:
            return {'status': 'ignore'}
        
        task_key = match.group(1)
        
        if not time_spent:
            return {'status': 'ignore'}
        
        time_str = ExcelParser._convert_time_to_jira(time_spent)
        if time_str == "ERROR":
            print(f"Invalid time format '{time_spent}' for task {task_key}")
            return {'status': 'ignore'}
        elif time_str is None:
            return {'status': 'ignore'}
        
        if not comment or comment.strip() == '':
            print(f"No comment for task {task_key} in row {idx + 1} - skipping")
            return {'status': 'skipped'}
        
        return {'status': 'worklog', 'worklog': WorklogEntry(task_key, comment, time_str, idx)}

    @staticmethod
    def _convert_time_to_jira(time_value) -> Optional[str]:
        try:
            if isinstance(time_value, str):
                if ':' in time_value:
                    parts = time_value.split(':')
                    hours, minutes = int(parts[0]), int(parts[1])
                else:
                    hours, minutes = int(float(time_value)), 0
            elif hasattr(time_value, 'hour'):
                hours, minutes = time_value.hour, time_value.minute
            else:
                hours, minutes = int(float(time_value)), 0
            
            if hours == 0 and minutes == 0:
                return None
            
            # Format as "Xh Ym" or just "Xh" or "Ym"
            if hours > 0 and minutes > 0:
                return f"{hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h"
            else:
                return f"{minutes}m"
        except Exception:
            return "ERROR"

class JiraClient:
    def __init__(self, base_url: str, credentials: str):
        self.base_url = base_url
        self.credentials = credentials

    def _call_jira_api(self, endpoint: str, method: str = 'GET', data: str = None, timeout: int = 30, debug: bool = False) -> Tuple[int, str, str, Optional[int]]:
        # Add -w flag to get HTTP response code
        cmd = ['curl', '-s', '-w', '%{http_code}', '-u', self.credentials]
        if method == 'POST':
            cmd.extend(['-X', 'POST', '-H', 'Content-Type: application/json'])
        if data:
            cmd.extend(['-d', data])
        cmd.append(f'{self.base_url}{endpoint}')
        
        if debug:
            # Hide credentials in debug output
            debug_cmd = cmd.copy()
            debug_cmd[debug_cmd.index('-u') + 1] = '***:***'
            print(f"DEBUG: {' '.join(debug_cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
            
            # Extract HTTP status code from end of response
            stdout = result.stdout
            http_code = None
            if len(stdout) >= 3 and stdout[-3:].isdigit():
                http_code = int(stdout[-3:])
                stdout = stdout[:-3]  # Remove HTTP code from response body
            
            return result.returncode, stdout, result.stderr, http_code
        except subprocess.TimeoutExpired:
            return -1, "", f"Timeout after {timeout} seconds", None

    def add_worklog(self, task_key: str, worklog: WorklogEntry, worklog_date: str = None) -> bool:
        data = worklog.to_jira_format(worklog_date)
        print(f"Adding worklog to {task_key}: {worklog.time_spent} (date: {data['started'][:10]})")
        
        code, stdout, stderr, http_code = self._call_jira_api(f'/rest/api/2/issue/{task_key}/worklog', 'POST', json.dumps(data))
        
        if code == 0:
            # Check HTTP status code first
            if http_code == 401:
                print(f"Authentication error for {task_key}: 401 Unauthorized - check credentials")
                return False
            elif http_code == 403:
                print(f"Permission error for {task_key}: 403 Forbidden - insufficient permissions")
                return False
            elif http_code == 404:
                print(f"Not found error for {task_key}: 404 Not Found - issue may not exist")
                return False
            elif http_code and (http_code < 200 or http_code >= 300):
                print(f"HTTP error for {task_key}: {http_code}")
                return False
            
            # Check if response is HTML (error page) instead of JSON
            if stdout.strip().startswith('<html>') or stdout.strip().startswith('<!DOCTYPE'):
                print(f"Authentication error for {task_key}: Received HTML error page")
                return False
            
            try:
                response_data = json.loads(stdout)
                # Check for error messages first
                if 'errorMessages' in response_data or 'errors' in response_data:
                    error_msg = response_data.get('errorMessages', response_data.get('errors', 'Unknown error'))
                    print(f"Jira error for {task_key}: {error_msg}")
                    return False
                # Check for successful response (should have 'id' field)
                elif 'id' in response_data:
                    worklog_id = response_data['id']
                    print(f"Successfully added worklog to {task_key} (ID: {worklog_id})")
                    return True
                else:
                    print(f"Unexpected response for {task_key}: {stdout[:200]}")
                    return False
            except json.JSONDecodeError:
                # Not valid JSON - could be HTML error page or other non-JSON response
                if 'Unauthorized' in stdout or '401' in stdout:
                    print(f"Authentication error for {task_key}: 401 Unauthorized")
                elif 'Forbidden' in stdout or '403' in stdout:
                    print(f"Permission error for {task_key}: 403 Forbidden")
                elif stderr:
                    print(f"Curl error for {task_key}: {stderr}")
                else:
                    print(f"Invalid response for {task_key}: {stdout[:200]}")
                return False
        
        print(f"{'Timeout' if code == -1 else 'Curl error'} adding worklog to {task_key}: {stderr}")
        return False

class WorklogProcessor:
    def __init__(self):
        self.jira_client = None
        self.sync_logger = SyncLogger()

    def initialize_jira(self) -> bool:
        if not Config.JIRA_CREDENTIALS or ':' not in Config.JIRA_CREDENTIALS:
            print("Missing Jira credentials. Use --jira-credentials login:password")
            return False
        
        if Config.JIRA_BASE_URL == "https://your-jira-server.com":
            print("Jira URL not configured! Set Config.JIRA_BASE_URL")
            return False
        
        print(f"Connecting to: {Config.JIRA_BASE_URL} as {Config.JIRA_CREDENTIALS.split(':')[0]}")
        self.jira_client = JiraClient(Config.JIRA_BASE_URL, Config.JIRA_CREDENTIALS)
        return True

    def process_file(self, date_str: str) -> bool:
        try:
            file_path = os.path.join(Config.INPUT_DIR, f"{date_str}.xlsx")
            if not os.path.exists(file_path):
                print(f"File does not exist: {file_path}")
                return False
            
            print(f"Processing file: {file_path}")
            df, worklogs, skipped_count = ExcelParser.parse_file(file_path)
            
            if not worklogs:
                print("No worklogs to process")
                return True
            
            failed_count = self._process_worklogs(date_str, worklogs)
            
            synced_count = len([w for w in worklogs if self.sync_logger.is_task_synced(date_str, w)])
            print(f"Processing completed. Synchronized {synced_count}/{len(worklogs)} worklogs")
            
            # Only move file if all worklogs were processed successfully (synced or skipped for missing comments)
            if failed_count == 0:
                self._handle_file_movement(file_path, skipped_count)
            else:
                print(f"File kept in {Config.INPUT_DIR}/ - {failed_count} worklogs failed to synchronize")
            
            return True
        except Exception as e:
            print(f"Error processing file: {e}")
            return False

    def _process_worklogs(self, date_str: str, worklogs: List[WorklogEntry]) -> int:
        """Process worklogs and return count of failed synchronizations"""
        unsync_worklogs = [w for w in worklogs if not self.sync_logger.is_task_synced(date_str, w)]
        
        if not unsync_worklogs:
            print("All worklogs synchronized")
            return 0
        
        print(f"Found {len(unsync_worklogs)} unsynchronized worklogs")
        
        success_count = 0
        failed_count = 0
        
        for worklog in unsync_worklogs:
            if self.jira_client and self.jira_client.add_worklog(worklog.task_key, worklog, date_str):
                success_count += 1
                self.sync_logger.mark_task_synced(date_str, worklog)
            else:
                failed_count += 1
                print(f"Failed to add worklog to {worklog.task_key} - will retry on next run")
        
        print(f"Saved {success_count} synchronized worklogs to log")
        
        return failed_count

    def _handle_file_movement(self, file_path: str, skipped_count: int):
        if skipped_count > 0:
            print(f"File kept in {Config.INPUT_DIR}/ - {skipped_count} tasks need comments")
        else:
            os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(Config.OUTPUT_DIR, os.path.basename(file_path))
            
            if os.path.exists(output_path):
                print(f"Overwriting {output_path}")
            
            try:
                shutil.move(file_path, output_path)
                print(f"Moved to: {output_path}")
            except PermissionError:
                print(f"Cannot move {file_path} - close Excel first. Target: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Excel to Jira worklog automation')
    parser.add_argument('date', nargs='?', default=datetime.now().strftime('%Y%m%d'), help='Date in YYYYMMDD format')
    parser.add_argument('--jira-credentials', help='Jira credentials in format login:password')
    
    args = parser.parse_args()
    
    if args.jira_credentials:
        Config.JIRA_CREDENTIALS = args.jira_credentials
    
    processor = WorklogProcessor()
    
    if not processor.initialize_jira():
        return 1
    
    success = processor.process_file(args.date)
    return 0 if success else 1

if __name__ == "__main__":

    sys.exit(main())
