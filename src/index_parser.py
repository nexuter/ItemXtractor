"""
SEC EDGAR Full-Index Parser - Retrieves all companies from quarterly index files
"""

import requests
import re
from typing import List, Set, Dict, Tuple
from script.config import SEC_BASE_URL, SEC_USER_AGENT, REQUEST_TIMEOUT, REQUEST_DELAY
import time


class SECIndexParser:
    """Parses SEC EDGAR full-index files to get all companies for a filing type"""
    
    def __init__(self, user_agent: str = SEC_USER_AGENT):
        """
        Initialize SECIndexParser
        
        Args:
            user_agent: User agent string for SEC requests
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})
    
    def _download_index_file(self, year: int, quarter: int) -> str:
        """
        Download company.idx file for a specific year and quarter
        
        Args:
            year: Year (e.g., 2023)
            quarter: Quarter (1-4)
            
        Returns:
            Content of the index file as string
            
        Raises:
            Exception if download fails
        """
        url = f"{SEC_BASE_URL}/Archives/edgar/full-index/{year}/QTR{quarter}/company.idx"
        
        last_err = None
        for attempt in range(6):
            try:
                time.sleep(max(REQUEST_DELAY, 0.5) * (attempt + 1))
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                # 404 means quarter likely unavailable.
                if response.status_code == 404:
                    return ""
                # SEC can return throttling/service errors transiently.
                if response.status_code in {403, 429, 500, 502, 503, 504}:
                    last_err = f"{response.status_code} {response.reason}"
                    continue
                response.raise_for_status()
                return response.text
            except Exception as e:
                last_err = str(e)
                continue
        raise Exception(f"Failed to download index for {year} Q{quarter}: {last_err}")
    
    def _parse_index_file(self, content: str, filing_type: str) -> List[Dict[str, str]]:
        """
        Parse company.idx file and extract filings of specific type
        
        Args:
            content: Content of the index file
            filing_type: Filing type to filter (e.g., '10-K')
            
        Returns:
            List of dictionaries with company info
        """
        filings = []
        
        # Skip header lines (usually first 10 lines are headers)
        lines = content.split('\n')
        data_started = False
        
        for line in lines:
            # Header ends with a line of dashes
            if '---' in line:
                data_started = True
                continue
            
            if not data_started or not line.strip():
                continue
            
            # Parse line: Company Name | Form Type | CIK | Date Filed | File Name
            # Lines are fixed-width or pipe-separated (varies by year)
            parts = line.split('|') if '|' in line else None
            
            if parts and len(parts) >= 5:
                # Pipe-separated format
                company_name = parts[0].strip()
                form_type = parts[1].strip()
                cik = parts[2].strip()
                date_filed = parts[3].strip()
                file_name = parts[4].strip()
            else:
                # Fixed-width-ish format. Some SEC rows drift from the nominal
                # column offsets, so prefer parsing the tail fields with a
                # spacing-aware regex to preserve multi-token form types such as
                # "NT 10-K" and "10-K/A".
                company_name = ""
                form_type = ""
                cik = ""
                date_filed = ""
                file_name = ""

                row_match = re.match(
                    r"^(?P<company>.*?\S)\s{2,}"
                    r"(?P<form>[A-Z0-9][A-Z0-9/\- ]*?)\s{2,}"
                    r"(?P<cik>\d+)\s{2,}"
                    r"(?P<date>\d{4}-\d{2}-\d{2})\s{2,}"
                    r"(?P<file>\S+)\s*$",
                    line.strip(),
                )
                if row_match:
                    company_name = row_match.group("company").strip()
                    form_type = row_match.group("form").strip()
                    cik = row_match.group("cik").strip()
                    date_filed = row_match.group("date").strip()
                    file_name = row_match.group("file").strip()
                else:
                    # Fall back to SEC's nominal fixed-width columns.
                    company_name = line[0:62].strip() if len(line) >= 62 else ""
                    form_type = line[62:74].strip() if len(line) >= 74 else ""
                    cik = line[74:86].strip() if len(line) >= 86 else ""
                    date_filed = line[86:98].strip() if len(line) >= 98 else ""
                    file_name = line[98:].strip() if len(line) > 98 else ""

                    valid_fixed_width = (
                        bool(company_name)
                        and bool(form_type)
                        and bool(re.fullmatch(r"\d+", cik))
                        and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_filed))
                        and bool(file_name)
                    )
                    if not valid_fixed_width:
                        continue
            
            # Normalize and filter by filing type
            form_type = form_type.upper().strip()
            if form_type == filing_type.upper().strip():
                accession = self._extract_accession_from_file_name(file_name)
                # Normalize CIK (remove leading zeros for consistency)
                cik_normalized = cik.lstrip('0') or '0'
                
                filings.append({
                    'company_name': company_name,
                    'form_type': form_type,
                    'cik': cik_normalized,
                    'cik_padded': cik.zfill(10),
                    'date_filed': date_filed,
                    'file_name': file_name,
                    'accession_number': accession,
                })
        
        return filings

    def _extract_accession_from_file_name(self, file_name: str) -> str:
        """
        Extract accession number from SEC index file name path.

        Args:
            file_name: SEC index file_name field (usually .../0000123456-24-000123.txt)

        Returns:
            Accession number formatted with dashes, or empty string if not found.
        """
        if not file_name:
            return ""
        match = re.search(r'(\d{10}-\d{2}-\d{6})', file_name)
        if match:
            return match.group(1)
        return ""

    def get_filing_records_for_filing(self, filing_type: str, years: List[int]) -> List[Dict[str, str]]:
        """
        Get all filing records from SEC full-index for a filing type and years.

        Unlike get_all_companies_for_filing, this returns all filing records and
        does not deduplicate by CIK/year.

        Args:
            filing_type: Filing type (e.g., '10-K')
            years: List of years to scan (by filing date year / index year)

        Returns:
            List of filing records with cik/date_filed/file_name/accession_number.
        """
        all_records: List[Dict[str, str]] = []
        for year in years:
            for quarter in range(1, 5):
                try:
                    content = self._download_index_file(year, quarter)
                    if not content:
                        continue
                    records = self._parse_index_file(content, filing_type)
                    all_records.extend(records)
                except Exception as e:
                    print(f"Warning: Failed to process {year} Q{quarter}: {str(e)}")
                    continue
        all_records.sort(key=lambda x: x.get('date_filed', ''), reverse=True)
        return all_records
    
    def get_all_companies_for_filing(self, filing_type: str, years: List[int]) -> List[Dict[str, str]]:
        """
        Get all companies that filed a specific form type across multiple years
        
        Args:
            filing_type: Filing type (e.g., '10-K', '10-Q')
            years: List of years to search
            
        Returns:
            List of unique filings with company info, sorted by date
        """
        all_filings = []
        seen_combinations = set()  # Track (CIK, year) to avoid duplicates
        
        for year in years:
            for quarter in range(1, 5):  # Q1-Q4
                try:
                    # Download index file
                    content = self._download_index_file(year, quarter)
                    
                    if not content:
                        # Quarter not available (e.g., future quarter)
                        continue
                    
                    # Parse and filter
                    filings = self._parse_index_file(content, filing_type)
                    
                    # Add to results, avoiding duplicates
                    for filing in filings:
                        # Extract year from date_filed (format: YYYY-MM-DD)
                        filed_year = filing['date_filed'][:4] if filing['date_filed'] else str(year)
                        
                        # Create unique key
                        key = (filing['cik'], filed_year)
                        
                        if key not in seen_combinations:
                            seen_combinations.add(key)
                            all_filings.append(filing)
                    
                except Exception as e:
                    # Log error but continue with other quarters
                    print(f"Warning: Failed to process {year} Q{quarter}: {str(e)}")
                    continue
        
        # Sort by date filed
        all_filings.sort(key=lambda x: x['date_filed'], reverse=True)
        
        return all_filings
    
    def get_ciks_for_filing(self, filing_type: str, years: List[int]) -> List[str]:
        """
        Get list of unique CIKs that filed a specific form type
        
        Args:
            filing_type: Filing type (e.g., '10-K', '10-Q')
            years: List of years to search
            
        Returns:
            List of unique CIK numbers (padded to 10 digits)
        """
        filings = self.get_all_companies_for_filing(filing_type, years)
        
        # Extract unique CIKs
        ciks = sorted(set(filing['cik_padded'] for filing in filings))
        
        return ciks
    
    def estimate_filing_count(self, filing_type: str, years: List[int]) -> Tuple[int, int]:
        """
        Estimate the number of filings without downloading full indices
        
        Args:
            filing_type: Filing type (e.g., '10-K', '10-Q')
            years: List of years
            
        Returns:
            Tuple of (estimated_count, quarters_checked)
        """
        # For 10-K: typically 4000-5000 per year
        # For 10-Q: typically 12000-15000 per year (3 quarters × 4000-5000 companies)
        
        estimated_counts = {
            '10-K': 4500,  # Average per year
            '10-Q': 13500  # Average per year (3 quarters)
        }
        
        base_count = estimated_counts.get(filing_type, 5000)
        total_estimate = base_count * len(years)
        quarters = len(years) * 4
        
        return total_estimate, quarters
