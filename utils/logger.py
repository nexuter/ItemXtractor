"""
Logger for tracking extraction operations
"""

import logging
import json
import os
import threading
from datetime import datetime
from typing import Dict, Any, List
from config import LOGS_DIR, LOG_FORMAT, LOG_DATE_FORMAT


class ExtractionLogger:
    """Handles logging for SEC filing extraction operations"""
    
    def __init__(self, log_dir: str = LOGS_DIR):
        """
        Initialize ExtractionLogger
        
        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # Setup logger
        self.logger = logging.getLogger('ItemXtractor')
        self.logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (unique for each run)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"extraction_{timestamp}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Session data for report generation
        self.session_data = {
            'start_time': datetime.now().isoformat(),
            'parameters': {},
            'filings': []
        }
        self.lock = threading.Lock()
    
    def set_parameters(self, **kwargs) -> None:
        """
        Set execution parameters
        
        Args:
            **kwargs: Parameter key-value pairs
        """
        with self.lock:
            self.session_data['parameters'] = kwargs
            self.logger.info(f"Parameters: {json.dumps(kwargs, indent=2)}")
    
    def log_filing_start(self, cik_ticker: str, year: str, filing_type: str) -> Dict[str, Any]:
        """
        Log the start of a filing extraction
        
        Args:
            cik_ticker: CIK or ticker
            year: Filing year
            filing_type: Type of filing
            
        Returns:
            Filing record dictionary
        """
        with self.lock:
            filing_record = {
                'cik_ticker': cik_ticker,
                'year': year,
                'filing_type': filing_type,
                'start_time': datetime.now().isoformat(),
                'downloaded': False,
                'skipped_download': False,
                'toc_found': False,
                'items_extracted': [],
                'errors': [],
                'status': 'in_progress'
            }
            self.session_data['filings'].append(filing_record)
            self.logger.info(f"Starting extraction for {cik_ticker} {filing_type} {year}")
            return filing_record
    
    def log_download(self, filing_record: Dict[str, Any], downloaded: bool, 
                    skipped: bool = False, error: str = None) -> None:
        """
        Log download status
        
        Args:
            filing_record: Filing record dictionary
            downloaded: Whether file was successfully downloaded
            skipped: Whether download was skipped (file already exists)
            error: Error message if download failed
        """
        with self.lock:
            filing_record['downloaded'] = downloaded
            filing_record['skipped_download'] = skipped
            
            if error:
                filing_record['errors'].append(f"Download error: {error}")
                self.logger.error(f"Download failed for {filing_record['cik_ticker']} "
                                f"{filing_record['filing_type']} {filing_record['year']}: {error}")
            elif skipped:
                self.logger.info(f"Download skipped (file exists) for {filing_record['cik_ticker']} "
                               f"{filing_record['filing_type']} {filing_record['year']}")
            else:
                self.logger.info(f"Downloaded {filing_record['cik_ticker']} "
                               f"{filing_record['filing_type']} {filing_record['year']}")
    
    def log_toc_detection(self, filing_record: Dict[str, Any], found: bool, 
                         error: str = None) -> None:
        """
        Log Table of Contents detection
        
        Args:
            filing_record: Filing record dictionary
            found: Whether TOC was found
            error: Error message if detection failed
        """
        with self.lock:
            filing_record['toc_found'] = found
            
            if error:
                filing_record['errors'].append(f"TOC detection error: {error}")
                self.logger.error(f"TOC detection failed: {error}")
            elif not found:
                self.logger.warning(f"No TOC found in {filing_record['cik_ticker']} "
                                  f"{filing_record['filing_type']} {filing_record['year']}")
            else:
                self.logger.info(f"TOC found in {filing_record['cik_ticker']} "
                               f"{filing_record['filing_type']} {filing_record['year']}")
    
    def log_item_extraction(self, filing_record: Dict[str, Any], item_number: str, 
                           success: bool, error: str = None) -> None:
        """
        Log item extraction
        
        Args:
            filing_record: Filing record dictionary
            item_number: Item number extracted
            success: Whether extraction was successful
            error: Error message if extraction failed
        """
        with self.lock:
            if success:
                filing_record['items_extracted'].append(item_number)
                self.logger.info(f"Extracted Item {item_number} from {filing_record['cik_ticker']} "
                               f"{filing_record['filing_type']} {filing_record['year']}")
            else:
                error_msg = f"Item {item_number} extraction error: {error}"
                filing_record['errors'].append(error_msg)
                self.logger.error(error_msg)
    
    def log_filing_complete(self, filing_record: Dict[str, Any]) -> None:
        """
        Mark filing processing as complete
        
        Args:
            filing_record: Filing record dictionary
        """
        with self.lock:
            filing_record['end_time'] = datetime.now().isoformat()
            filing_record['status'] = 'completed'
            
            # Calculate duration
            start = datetime.fromisoformat(filing_record['start_time'])
            end = datetime.fromisoformat(filing_record['end_time'])
            duration = (end - start).total_seconds()
            filing_record['duration_seconds'] = duration
            
            self.logger.info(f"Completed {filing_record['cik_ticker']} "
                           f"{filing_record['filing_type']} {filing_record['year']} "
                           f"in {duration:.2f}s - Items: {filing_record['items_extracted']}")
    
    def generate_report(self) -> str:
        """
        Generate final execution report
        
        Returns:
            JSON report string
        """
        with self.lock:
            self.session_data['end_time'] = datetime.now().isoformat()
            
            # Calculate total duration
            start = datetime.fromisoformat(self.session_data['start_time'])
            end = datetime.fromisoformat(self.session_data['end_time'])
            total_duration = (end - start).total_seconds()
            self.session_data['total_duration_seconds'] = total_duration
            
            # Summary statistics
            total_filings = len(self.session_data['filings'])
            successful_downloads = sum(1 for f in self.session_data['filings'] if f['downloaded'] or f['skipped_download'])
            toc_found = sum(1 for f in self.session_data['filings'] if f['toc_found'])
            total_items = sum(len(f['items_extracted']) for f in self.session_data['filings'])
            
            self.session_data['summary'] = {
                'total_filings': total_filings,
                'successful_downloads': successful_downloads,
                'toc_found': toc_found,
                'total_items_extracted': total_items
            }
            
            # Save report to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(self.log_dir, f"report_{timestamp}.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Execution Report:")
            self.logger.info(f"  Total Duration: {total_duration:.2f}s")
            self.logger.info(f"  Total Filings: {total_filings}")
            self.logger.info(f"  Successful Downloads: {successful_downloads}")
            self.logger.info(f"  TOC Found: {toc_found}")
            self.logger.info(f"  Total Items Extracted: {total_items}")
            self.logger.info(f"  Report saved to: {report_file}")
            
            return json.dumps(self.session_data, indent=2)
    
    def info(self, message: str) -> None:
        """Log info message"""
        with self.lock:
            self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log warning message"""
        with self.lock:
            self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log error message"""
        with self.lock:
            self.logger.error(message)
