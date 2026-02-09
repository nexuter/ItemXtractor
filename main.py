"""
ItemXtractor - Main script for extracting items from SEC EDGAR filings

This script downloads SEC filings (10-K, 10-Q) and extracts specific items
using the Table of Contents to locate each item within the filing.
"""

import os
import sys
from typing import List, Optional, Union
from src.downloader import SECDownloader
from src.parser import SECParser
from src.extractor import ItemExtractor
from utils.logger import ExtractionLogger
from utils.file_manager import FileManager
from config import ITEMS_10K, ITEMS_10Q


class ItemXtractor:
    """Main class for extracting items from SEC EDGAR filings"""
    
    def __init__(self, base_dir: str = "sec_filings", log_dir: str = "logs"):
        """
        Initialize ItemXtractor
        
        Args:
            base_dir: Base directory for storing SEC filings
            log_dir: Directory for log files
        """
        self.downloader = SECDownloader()
        self.parser = SECParser()
        self.extractor = ItemExtractor()
        self.file_manager = FileManager(base_dir)
        self.logger = ExtractionLogger(log_dir)
    
    def _get_available_items(self, filing_type: str) -> List[str]:
        """
        Get list of available items for a filing type
        
        Args:
            filing_type: Type of filing (10-K or 10-Q)
            
        Returns:
            List of available item numbers
        """
        if filing_type == "10-K":
            return list(ITEMS_10K.keys())
        elif filing_type == "10-Q":
            return list(ITEMS_10Q.keys())
        else:
            return []
    
    def process_filing(self, cik_ticker: str, year: str, filing_type: str,
                      items: Optional[List[str]] = None) -> bool:
        """
        Process a single SEC filing
        
        Args:
            cik_ticker: CIK number or ticker symbol
            year: Filing year
            filing_type: Type of filing (10-K or 10-Q)
            items: List of item numbers to extract (None = extract all)
            
        Returns:
            True if successful, False otherwise
        """
        # Start logging for this filing
        filing_record = self.logger.log_filing_start(cik_ticker, year, filing_type)
        
        try:
            # Create directory structure upfront
            self.file_manager.create_directory_structure(cik_ticker, year, filing_type)
            
            # Determine file path - try both extensions
            filing_path_html = self.file_manager.get_filing_path(cik_ticker, year, filing_type, 'html')
            filing_path_htm = self.file_manager.get_filing_path(cik_ticker, year, filing_type, 'htm')
            
            # Check if file already exists (explicitly checking for FILES, not directories)
            if self.file_manager.file_exists(filing_path_html):
                self.logger.info(f"File found: {filing_path_html}")
                filing_path = filing_path_html
                html_content = self.file_manager.load_html(filing_path)
                self.logger.log_download(filing_record, True, skipped=True)
            elif self.file_manager.file_exists(filing_path_htm):
                self.logger.info(f"File found: {filing_path_htm}")
                filing_path = filing_path_htm
                html_content = self.file_manager.load_html(filing_path)
                self.logger.log_download(filing_record, True, skipped=True)
            else:
                # Files don't exist, so download them
                self.logger.info(f"Files not found. Will attempt download:")
                self.logger.info(f"  Looking for: {filing_path_html}")
                self.logger.info(f"  Or: {filing_path_htm}")
                
                # Download the filing
                try:
                    html_content, extension, _ = self.downloader.download_filing(
                        cik_ticker, filing_type, year
                    )
                    
                    filing_path = self.file_manager.get_filing_path(
                        cik_ticker, year, filing_type, extension
                    )
                    self.file_manager.save_html(filing_path, html_content)
                    self.logger.log_download(filing_record, True, skipped=False)
                except Exception as e:
                    self.logger.log_download(filing_record, False, error=str(e))
                    self.logger.log_filing_complete(filing_record)
                    return False
            
            # Parse Table of Contents
            try:
                toc_items = self.parser.parse_toc(html_content, filing_type)
                
                if toc_items:
                    self.logger.log_toc_detection(filing_record, True)
                else:
                    self.logger.log_toc_detection(filing_record, False)
                    self.logger.log_filing_complete(filing_record)
                    return False
                    
            except Exception as e:
                self.logger.log_toc_detection(filing_record, False, error=str(e))
                self.logger.log_filing_complete(filing_record)
                return False
            
            # Determine which items to extract
            if items is None:
                # Extract all items found in TOC
                items_to_extract = list(toc_items.keys())
            else:
                # Only extract requested items that exist in TOC
                items_to_extract = [item for item in items if item in toc_items]
            
            # Extract items
            for item_number in items_to_extract:
                try:
                    item_data = self.extractor.extract_item(
                        html_content, item_number, toc_items
                    )
                    
                    # Save to JSON
                    item_path = self.file_manager.get_item_path(
                        cik_ticker, year, filing_type, item_number
                    )
                    self.file_manager.save_item_json(item_path, item_data)
                    
                    self.logger.log_item_extraction(filing_record, item_number, True)
                    
                except Exception as e:
                    self.logger.log_item_extraction(
                        filing_record, item_number, False, error=str(e)
                    )
            
            self.logger.log_filing_complete(filing_record)
            return True
            
        except Exception as e:
            filing_record['errors'].append(f"Unexpected error: {str(e)}")
            self.logger.error(f"Unexpected error processing filing: {str(e)}")
            self.logger.log_filing_complete(filing_record)
            return False
    
    def extract(self, cik_tickers: Union[str, List[str]], 
                filing_types: Union[str, List[str]],
                years: Union[str, int, List[Union[str, int]]],
                items: Optional[List[str]] = None) -> str:
        """
        Extract items from SEC filings
        
        Args:
            cik_tickers: CIK number(s) or ticker symbol(s)
            filing_types: Filing type(s) (10-K, 10-Q)
            years: Year(s) to extract
            items: List of item numbers to extract (None = extract all)
            
        Returns:
            JSON report string
        """
        # Normalize inputs to lists
        if isinstance(cik_tickers, str):
            cik_tickers = [cik_tickers]
        if isinstance(filing_types, str):
            filing_types = [filing_types]
        if isinstance(years, (str, int)):
            years = [str(years)]
        else:
            years = [str(year) for year in years]
        
        # Log parameters
        self.logger.set_parameters(
            cik_tickers=cik_tickers,
            filing_types=filing_types,
            years=years,
            items=items if items else "all"
        )
        
        # Process each combination
        for cik_ticker in cik_tickers:
            for filing_type in filing_types:
                for year in years:
                    self.process_filing(cik_ticker, year, filing_type, items)
        
        # Generate and return report
        return self.logger.generate_report()


def main():
    """Main entry point for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Extract items from SEC EDGAR filings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all items from Apple's 2023 10-K
  python main.py --ticker AAPL --filing 10-K --year 2023
  
  # Extract specific items from Microsoft's 2022 and 2023 10-K
  python main.py --ticker MSFT --filing 10-K --years 2022 2023 --items 1 1A 7
  
  # Extract from multiple companies
  python main.py --tickers AAPL MSFT GOOGL --filing 10-K --year 2023
  
  # Use CIK instead of ticker
  python main.py --cik 0000320193 --filing 10-K --year 2023
        """
    )
    
    # Company identifiers
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--ticker', '--tickers', nargs='+', dest='tickers',
                      help='Stock ticker symbol(s)')
    group.add_argument('--cik', '--ciks', nargs='+', dest='ciks',
                      help='CIK number(s)')
    
    # Filing parameters
    parser.add_argument('--filing', '--filings', nargs='+', dest='filings',
                       required=True, choices=['10-K', '10-Q'],
                       help='Filing type(s)')
    parser.add_argument('--year', '--years', nargs='+', dest='years',
                       required=True, help='Year(s) to extract')
    parser.add_argument('--items', nargs='+', dest='items', default=None,
                       help='Item number(s) to extract (omit to extract all items)')
    
    # Directories
    parser.add_argument('--output-dir', default='sec_filings',
                       help='Output directory for filings (default: sec_filings)')
    parser.add_argument('--log-dir', default='logs',
                       help='Log directory (default: logs)')
    
    args = parser.parse_args()
    
    # Convert years to integers
    years = [int(y) for y in args.years]
    
    # Validate years
    for year in years:
        if year < 1995 or year > 2025:
            parser.error(f"Year {year} must be between 1995 and 2025")
    
    # Get company identifiers
    companies = args.tickers if args.tickers else args.ciks
    
    # Create extractor
    extractor = ItemXtractor(base_dir=args.output_dir, log_dir=args.log_dir)
    
    # Run extraction
    extractor.extract(
        cik_tickers=companies,
        filing_types=args.filings,
        years=years,
        items=args.items
    )


if __name__ == "__main__":
    main()
