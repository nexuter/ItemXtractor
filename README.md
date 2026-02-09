# ItemXtractor

A professional Python tool for extracting specific items from SEC EDGAR 10-K and 10-Q filings. ItemXtractor automatically downloads filings, detects the Table of Contents, and extracts individual items into structured JSON format with both HTML and plain text content.

## Features

- 🎯 **Smart Extraction**: Uses Table of Contents to accurately locate and extract specific items
- 📊 **Multiple Filing Types**: Supports both 10-K and 10-Q filings
- 🔄 **Batch Processing**: Extract from multiple companies, years, and filings in one command
- 💾 **Skip Downloads**: Automatically skips re-downloading existing files
- 📝 **Comprehensive Logging**: Detailed logs and JSON reports for each extraction session
- 🎨 **Dual Format Output**: Each item saved as both HTML and plain text in JSON
- 🔍 **CIK or Ticker**: Works with both CIK numbers and stock ticker symbols
- ✓ **Amendment Filtering**: Automatically skips amended filings (10-K/A, 10-Q/A), selecting regular filings
- 🛡️ **Robust Boundary Detection**: Handles edge cases with ID-based markers and HTML parsing variations
- 📚 **Hierarchical Structure Extraction**: Automatically detects and extracts nested heading-body pairs from items with multi-level hierarchies

## Installation

### Prerequisites

- Python 3.7 or higher
- pip

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ItemXtractor.git
cd ItemXtractor
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. **Important**: Update the User-Agent in `config.py`:
```python
SEC_USER_AGENT = "ItemXtractor/1.0 (Research Tool; your.email@domain.com)"
```
The SEC requires a valid email in the User-Agent header.

## Quick Start

### Command Line Usage

Extract all items from Apple's 2023 10-K:
```bash
python main.py --ticker AAPL --filing 10-K --year 2023
```

Extract specific items (Risk Factors and MD&A) from Microsoft's 2023 10-K:
```bash
python main.py --ticker MSFT --filing 10-K --year 2023 --items 1A 7
```

Extract from multiple companies and years:
```bash
python main.py --tickers AAPL MSFT GOOGL --filing 10-K --years 2022 2023
```

### Python API Usage

```python
from main import ItemXtractor

# Create extractor instance
extractor = ItemXtractor()

# Extract all items from a filing
extractor.extract(
    cik_tickers="AAPL",
    filing_types="10-K",
    years=2023,
    items=None  # None = extract all items
)

# Extract specific items
extractor.extract(
    cik_tickers=["AAPL", "MSFT"],
    filing_types="10-K",
    years=[2022, 2023],
    items=["1", "1A", "7"]  # Business, Risk Factors, MD&A
)
```

## File Structure

Extracted filings and items are organized as follows:

```
sec_filings/
├── AAPL/
│   └── 2023/
│       └── 10-K/
│           ├── AAPL_2023_10-K.html          # Original filing
│           └── items/
│               ├── AAPL_2023_10-K_item1.json
│               ├── AAPL_2023_10-K_item1A.json
│               ├── AAPL_2023_10-K_item7.json
│               └── ...
└── MSFT/
    └── 2023/
        └── 10-Q/
            ├── MSFT_2023_10-Q.html
            └── items/
                └── ...
```

### Structure Extraction

After extracting items, you can extract hierarchical heading-body pair structures from within each item. This is useful for further analysis of complex items like Item 1 (Business).

Extract hierarchical structures from already extracted items:
```bash
python main.py --ticker AAPL --filing 10-K --year 2022 --extract-structure
```

This creates `*_xtr.json` files alongside the original item files, containing the hierarchical structure:

```json
{
  "ticker": "AAPL",
  "year": "2022",
  "filing_type": "10-K",
  "item_number": "1",
  "structure": [
    {
      "type": "bold_heading",
      "layer": 1,
      "heading": "Products",
      "body": "",
      "children": [
        {
          "type": "heading",
          "layer": 2,
          "heading": "iPhone",
          "body": "iPhone® is the Company's line of smartphones...",
          "children": []
        },
        {
          "type": "heading",
          "layer": 2,
          "heading": "Mac",
          "body": "Mac® is the Company's line of personal computers...",
          "children": []
        }
      ]
    }
  ]
}
```

**How it works:**
- Level 1 headings are bold styled divs (font-weight:700)
- Level 2 headings are italic styled divs (font-style:italic) nested under level 1
- Each heading captures the body content until the next heading at same or higher level
- Supports arbitrary nesting depth for complex documents

**Example - AAPL 2022 Item 1 structure:**
- Item 1. Business (level 1)
  - Company Background (level 1)
  - Products (level 1)
    - iPhone (level 2)
    - Mac (level 2)
    - iPad (level 2)
    - Wearables, Home and Accessories (level 2)
  - Services (level 1)
    - Advertising (level 2)
    - AppleCare (level 2)
    - Cloud Services (level 2)
    - Digital Content (level 2)
    - Payment Services (level 2)
  - Human Capital (level 1)
    - Workplace Practices and Policies (level 2)
    - Compensation and Benefits (level 2)
    - Inclusion and Diversity (level 2)
    - Engagement (level 2)
    - Health and Safety (level 2)

```

## Available Items

### 10-K Filing Items

| Item | Description |
|------|-------------|
| 1    | Business |
| 1A   | Risk Factors |
| 1B   | Unresolved Staff Comments |
| 1C   | Cybersecurity |
| 2    | Properties |
| 3    | Legal Proceedings |
| 4    | Mine Safety Disclosures |
| 5    | Market for Registrant's Common Equity |
| 6    | Selected Financial Data (removed in newer filings) |
| 7    | Management's Discussion and Analysis |
| 7A   | Quantitative and Qualitative Disclosures About Market Risk |
| 8    | Financial Statements and Supplementary Data |
| 9    | Changes in and Disagreements with Accountants |
| 9A   | Controls and Procedures |
| 9B   | Other Information |
| 10   | Directors, Executive Officers and Corporate Governance |
| 11   | Executive Compensation |
| 12   | Security Ownership of Certain Beneficial Owners and Management |
| 13   | Certain Relationships and Related Transactions |
| 14   | Principal Accounting Fees and Services |
| 15   | Exhibits, Financial Statement Schedules |
| 16   | Form 10-K Summary |

### 10-Q Filing Items

| Item | Description |
|------|-------------|
| 1    | Financial Statements |
| 2    | Management's Discussion and Analysis |
| 3    | Quantitative and Qualitative Disclosures About Market Risk |
| 4    | Controls and Procedures |

## Command Line Options

```
usage: main.py [-h] (--ticker TICKERS [TICKERS ...] | --cik CIKS [CIKS ...])
               --filing {10-K,10-Q} [{10-K,10-Q} ...]
               --year YEARS [YEARS ...]
               [--items ITEMS [ITEMS ...]]
               [--output-dir OUTPUT_DIR]
               [--log-dir LOG_DIR]

Extract items from SEC EDGAR filings

optional arguments:
  -h, --help            show this help message and exit
  --ticker TICKERS [TICKERS ...], --tickers TICKERS [TICKERS ...]
                        Stock ticker symbol(s)
  --cik CIKS [CIKS ...], --ciks CIKS [CIKS ...]
                        CIK number(s)
  --filing {10-K,10-Q} [{10-K,10-Q} ...], --filings {10-K,10-Q} [{10-K,10-Q} ...]
                        Filing type(s)
  --year YEARS [YEARS ...], --years YEARS [YEARS ...]
                        Year(s) to extract
  --items ITEMS [ITEMS ...]
                        Item number(s) to extract (default: all)
  --output-dir OUTPUT_DIR
                        Output directory for filings (default: sec_filings)
  --log-dir LOG_DIR     Log directory (default: logs)
```

## Logging and Reports

ItemXtractor generates comprehensive logs for every extraction session:

- **Console logs**: Real-time progress output
- **Log files**: Detailed logs saved in `logs/extraction_YYYYMMDD_HHMMSS.log`
- **JSON reports**: Summary reports saved in `logs/report_YYYYMMDD_HHMMSS.json`

### Report Contents

Each JSON report includes:
- Parameters used for extraction
- Start and end timestamps
- Total duration
- For each filing:
  - Download status (new download or skipped)
  - TOC detection results
  - Successfully extracted items
  - Any errors encountered
  - Processing time

## Usage Examples

For programmatic use, import and instantiate the `ItemXtractor` class:

```python
from main import ItemXtractor

extractor = ItemXtractor()
extractor.extract(
    cik_tickers="AAPL",
    filing_types="10-K",
    years=2022,
    items=["1", "1A", "7"]
)
```

## How It Works

1. **Resolution**: Converts ticker symbols to CIK numbers using SEC's company tickers API
2. **Download**: Fetches the filing HTML from SEC EDGAR (or skips if already downloaded)
   - **Amendment Filtering**: Checks document types and skips amended filings (10-K/A, 10-Q/A)
3. **TOC Detection**: Intelligently locates the Table of Contents in the filing
4. **Parsing**: Extracts anchor links and positions for each item from the TOC
5. **Extraction**: Uses TOC information to accurately split the filing into individual items
   - **ID-Based Boundary Detection**: Uses HTML element IDs (signatures, exhibits, cover) for precise item boundaries
   - **Fallback Patterns**: Handles cases where text spans multiple HTML tags
6. **Conversion**: Generates both HTML and plain text versions of each item
7. **Storage**: Saves each item as a structured JSON file
8. **Logging**: Records all activities and generates a comprehensive report

## Requirements

- `requests>=2.31.0` - HTTP requests to SEC EDGAR
- `beautifulsoup4>=4.12.0` - HTML parsing
- `lxml>=4.9.0` - Fast XML/HTML parsing
- `html5lib>=1.1` - HTML5 parsing support

## SEC API Guidelines

This tool follows SEC EDGAR's API guidelines:
- Maximum 10 requests per second (configurable in `config.py`)
- Declares a User-Agent header with contact information
- Respects robots.txt

**Please update the User-Agent with your email before using this tool.**

## Limitations

- **TOC Dependency**: If a filing doesn't have a detectable Table of Contents, items cannot be extracted. The tool will log this and skip extraction.
- **Format Variations**: SEC filings vary in format. While the tool handles most common formats, some unusual formats may not parse correctly.
- **Historical Filings**: Very old filings may have different structures. The tool is optimized for recent filings (2010+).

## Troubleshooting

### Amendment Filings
- The tool automatically filters out amended filings (10-K/A, 10-Q/A) and selects the original filing type
- This ensures you get the current, non-amended version of the filing

### Item Boundaries and Signatures Section
- The tool uses ID-based markers in HTML elements to detect item boundaries precisely
- This handles edge cases where text (like "SIGNATURES") is split across multiple HTML tags
- If Item 16 is extracted, it correctly stops before the SIGNATURES section

### No TOC Found

If the tool reports "No TOC found":
- The filing may use an unusual format
- Try manually inspecting the HTML file in `sec_filings/`
- Some filings don't have a traditional TOC

### Item Not Extracted

If specific items aren't extracted:
- Check the log file for errors
- Verify the item exists in that filing type (10-K vs 10-Q have different items)
- The TOC may not include that item number

### Download Failures

If downloads fail:
- Check your internet connection
- Verify the ticker/CIK is correct
- Ensure you've updated the User-Agent with a valid email
- The filing may not exist for that year

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is provided as-is for research purposes. Please ensure compliance with SEC EDGAR's terms of service and applicable data usage policies.

## Acknowledgments

- SEC EDGAR for providing free access to financial filings
- Beautiful Soup for HTML parsing capabilities

## Contact

For issues, questions, or contributions, please use the GitHub issue tracker.

---

**Disclaimer**: This tool is for research and educational purposes. Always verify extracted data against original SEC filings. The authors are not responsible for any decisions made based on data extracted using this tool.
