"""
Filing Analysis Statistics Generator
Analyzes downloaded SEC filings and generates comprehensive descriptive statistics report
"""

import os
import json
import csv
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import statistics

class FilingAnalyzer:
    """Analyzes SEC filings and generates statistics report"""
    
    def __init__(self, filings_folder):
        self.filings_folder = Path(filings_folder)
        self.stats = {
            'filings': defaultdict(lambda: defaultdict(int)),
            'items': defaultdict(lambda: {
                'success': 0,
                'failed': 0,
                'headings': [],
                'bodies': [],
                'elements': [],
                'depths': []
            }),
            'files': {
                'sizes': [],
                'item_sizes': defaultdict(list),
                'structure_sizes': defaultdict(list)
            },
            'years': set(),
            'ciks': set()
        }
        self.report = []
        
    def analyze(self):
        """Run complete analysis"""
        print("Scanning filings folder...")
        self._scan_filings()
        
        print("Analyzing structure files...")
        self._analyze_structures()
        
        print("Generating report...")
        self._generate_report()
        
        return self._write_report()
    
    def _scan_filings(self):
        """Scan filings folder and collect statistics"""
        if not self.filings_folder.exists():
            raise Exception(f"Folder not found: {self.filings_folder}")
        
        # Walk through folder structure: {cik}/{year}/{filing_type}/
        for cik_folder in self.filings_folder.iterdir():
            if not cik_folder.is_dir() or cik_folder.name.startswith('.'):
                continue
            
            cik = cik_folder.name
            self.stats['ciks'].add(cik)
            
            for year_folder in cik_folder.iterdir():
                if not year_folder.is_dir():
                    continue
                
                try:
                    year = int(year_folder.name)
                except ValueError:
                    continue
                
                self.stats['years'].add(year)
                
                for filing_folder in year_folder.iterdir():
                    if not filing_folder.is_dir():
                        continue
                    
                    filing_type = filing_folder.name
                    self.stats['filings'][year][filing_type] += 1
                    
                    # Scan items folder
                    items_folder = filing_folder / 'items'
                    if items_folder.exists():
                        self._analyze_items_folder(items_folder, year, filing_type, cik)
                    
                    # Get filing size
                    for html_file in filing_folder.glob('*.[hH][tT][mM]*'):
                        if html_file.is_file():
                            self.stats['files']['sizes'].append(html_file.stat().st_size)
    
    def _analyze_items_folder(self, items_folder, year, filing_type, cik):
        """Analyze items in a filing folder"""
        for item_file in items_folder.glob('*_item*.json'):
            if item_file.name.endswith('_xtr.json'):
                continue  # Skip structure files for now
            
            # Extract item number from filename
            # Format: {CIK}_{year}_{filing_type}_item{num}.json
            parts = item_file.stem.split('_item')
            if len(parts) < 2:
                continue
            
            item_num = parts[-1]
            
            # Count by file existence instead of reading
            self.stats['items'][item_num]['success'] += 1
            self.stats['files']['item_sizes'][item_num].append(item_file.stat().st_size)
    
    def _analyze_structures(self):
        """Analyze structure files (*_xtr.json)"""
        for cik_folder in self.filings_folder.iterdir():
            if not cik_folder.is_dir() or cik_folder.name.startswith('.'):
                continue
            
            for year_folder in cik_folder.iterdir():
                if not year_folder.is_dir():
                    continue
                
                for filing_folder in year_folder.iterdir():
                    if not filing_folder.is_dir():
                        continue
                    
                    items_folder = filing_folder / 'items'
                    if not items_folder.exists():
                        continue
                    
                    for xtr_file in items_folder.glob('*_xtr.json'):
                        self._analyze_structure_file(xtr_file)
    
    def _analyze_structure_file(self, xtr_file):
        """Analyze a single structure file"""
        try:
            with open(xtr_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            item_num = data.get('item_number', 'Unknown')
            structure = data.get('structure', [])
            
            if structure:
                # Count headings and bodies
                headings = self._count_headings(structure)
                bodies = self._count_bodies(structure)
                depth = self._max_depth(structure)
                
                self.stats['items'][item_num]['headings'].append(headings)
                self.stats['items'][item_num]['bodies'].append(bodies)
                self.stats['items'][item_num]['elements'].append(len(self._flatten_structure(structure)))
                self.stats['items'][item_num]['depths'].append(depth)
                
                self.stats['files']['structure_sizes'][item_num].append(xtr_file.stat().st_size)
        except Exception as e:
            pass
    
    def _count_headings(self, structure, bold_only=False):
        """Count headings in structure"""
        count = 0
        for elem in structure:
            if elem.get('type') in ['heading', 'bold_heading']:
                if not bold_only or elem.get('type') == 'bold_heading':
                    count += 1
            if 'children' in elem:
                count += self._count_headings(elem['children'], bold_only)
        return count
    
    def _count_bodies(self, structure):
        """Count non-empty bodies in structure"""
        count = 0
        for elem in structure:
            if elem.get('body', '').strip():
                count += 1
            if 'children' in elem:
                count += self._count_bodies(elem['children'])
        return count
    
    def _max_depth(self, structure, depth=0):
        """Get maximum nesting depth"""
        max_d = depth
        for elem in structure:
            if 'children' in elem:
                max_d = max(max_d, self._max_depth(elem['children'], depth + 1))
        return max_d
    
    def _flatten_structure(self, structure):
        """Flatten structure to count all elements"""
        elements = []
        for elem in structure:
            elements.append(elem)
            if 'children' in elem:
                elements.extend(self._flatten_structure(elem['children']))
        return elements
    
    def _generate_report(self):
        """Generate markdown report"""
        self.report = []
        
        # Header
        self.report.append("# Filing Analysis Report")
        self.report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.report.append("")
        
        # Executive Summary
        self._add_executive_summary()
        
        # Year-by-Year Overview
        self._add_year_overview()
        
        # Item Extraction Analysis
        self._add_item_extraction()
        
        # File Statistics
        self._add_file_statistics()
        
        # Structure Extraction Analysis
        self._add_structure_analysis()
        
        # Headings & Bodies Analysis
        self._add_headings_bodies_analysis()
        
        # Item Statistics Heatmap
        self._add_item_heatmap()
        
        # Conclusions
        self._add_conclusions()
    
    def _add_executive_summary(self):
        """Add executive summary section"""
        self.report.append("## 1. Executive Summary")
        self.report.append("")
        
        total_filings = sum(sum(v.values()) for v in self.stats['filings'].values())
        years = sorted(self.stats['years'])
        total_size = sum(self.stats['files']['sizes']) / (1024**3)  # GB
        
        self.report.append(f"- **Total Filings Analyzed**: {total_filings:,}")
        self.report.append(f"- **Unique Companies (CIKs)**: {len(self.stats['ciks']):,}")
        self.report.append(f"- **Years Covered**: {years[0]}-{years[-1]}")
        self.report.append(f"- **Total Storage Used**: {total_size:.1f} GB")
        self.report.append(f"- **Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.report.append("")
    
    def _add_year_overview(self):
        """Add year-by-year overview"""
        self.report.append("## 2. Year-by-Year Overview")
        self.report.append("")
        
        for year in sorted(self.stats['years']):
            total = sum(self.stats['filings'][year].values())
            self.report.append(f"### {year} ({total:,} filings)")
            self.report.append("")
            
            for filing_type, count in self.stats['filings'][year].items():
                self.report.append(f"- **{filing_type}**: {count:,} filings")
            
            self.report.append("")
    
    def _add_item_extraction(self):
        """Add item extraction analysis"""
        self.report.append("## 3. Item Extraction Analysis")
        self.report.append("")
        
        self.report.append("### Extraction Success Rates")
        self.report.append("")
        self.report.append("| Item | Success | Failed | Success Rate |")
        self.report.append("|------|---------|--------|--------------|")
        
        for item in sorted(self.stats['items'].keys()):
            success = self.stats['items'][item]['success']
            failed = self.stats['items'][item]['failed']
            total = success + failed
            if total > 0:
                rate = (success / total) * 100
                self.report.append(f"| Item {item} | {success:,} | {failed:,} | {rate:.1f}% |")
        
        self.report.append("")
    
    def _add_file_statistics(self):
        """Add file statistics"""
        self.report.append("## 4. File Statistics")
        self.report.append("")
        
        if self.stats['files']['sizes']:
            sizes_mb = [s / (1024**2) for s in self.stats['files']['sizes']]
            avg_size = statistics.mean(sizes_mb)
            median_size = statistics.median(sizes_mb)
            min_size = min(sizes_mb)
            max_size = max(sizes_mb)
            
            self.report.append("### Filing Size Metrics")
            self.report.append("")
            self.report.append(f"- **Average Filing Size**: {avg_size:.2f} MB")
            self.report.append(f"- **Median Filing Size**: {median_size:.2f} MB")
            self.report.append(f"- **Min Filing Size**: {min_size:.2f} MB")
            self.report.append(f"- **Max Filing Size**: {max_size:.2f} MB")
            self.report.append("")
        
        self.report.append("### Item JSON File Sizes")
        self.report.append("")
        self.report.append("| Item | Avg Size | Min Size | Max Size |")
        self.report.append("|------|----------|----------|----------|")
        
        for item in sorted(self.stats['files']['item_sizes'].keys()):
            sizes = [s / 1024 for s in self.stats['files']['item_sizes'][item]]
            if sizes:
                avg = statistics.mean(sizes)
                min_s = min(sizes)
                max_s = max(sizes)
                self.report.append(f"| Item {item} | {avg:.1f} KB | {min_s:.1f} KB | {max_s:.1f} KB |")
        
        self.report.append("")
    
    def _add_structure_analysis(self):
        """Add structure extraction analysis"""
        self.report.append("## 5. Structure Extraction Analysis")
        self.report.append("")
        
        self.report.append("### Structure Files Created")
        self.report.append("")
        
        total_structures = sum(len(v) for v in self.stats['files']['structure_sizes'].values())
        self.report.append(f"- **Total Structure Files**: {total_structures:,}")
        self.report.append("")
        
        self.report.append("### Average Metrics by Item")
        self.report.append("")
        self.report.append("| Item | Avg Depth | Max Depth | Avg Elements |")
        self.report.append("|------|-----------|-----------|--------------|")
        
        for item in sorted(self.stats['items'].keys()):
            depths = self.stats['items'][item]['depths']
            elements = self.stats['items'][item]['elements']
            
            if depths and elements:
                avg_depth = statistics.mean(depths)
                max_depth = max(depths) if depths else 0
                avg_elems = statistics.mean(elements)
                self.report.append(f"| Item {item} | {avg_depth:.1f} | {max_depth} | {avg_elems:.0f} |")
        
        self.report.append("")
    
    def _add_headings_bodies_analysis(self):
        """Add headings and bodies analysis"""
        self.report.append("## 6. Headings & Bodies Analysis by Item")
        self.report.append("")
        
        self.report.append("### Item-by-Item Heading & Body Breakdown")
        self.report.append("")
        self.report.append("| Item | Avg Headings | Avg Bodies | H/B Ratio | Avg Elements |")
        self.report.append("|------|-------------|-----------|-----------|--------------|")
        
        for item in sorted(self.stats['items'].keys()):
            headings = self.stats['items'][item]['headings']
            bodies = self.stats['items'][item]['bodies']
            elements = self.stats['items'][item]['elements']
            
            if headings and bodies:
                avg_h = statistics.mean(headings)
                avg_b = statistics.mean(bodies)
                ratio = avg_h / avg_b if avg_b > 0 else 0
                avg_e = statistics.mean(elements)
                
                self.report.append(f"| Item {item} | {avg_h:.1f} | {avg_b:.1f} | 1:{ratio:.1f} | {avg_e:.0f} |")
        
        self.report.append("")
        
        # Global metrics
        all_headings = []
        all_bodies = []
        all_elements = []
        
        for item in self.stats['items'].values():
            all_headings.extend(item['headings'])
            all_bodies.extend(item['bodies'])
            all_elements.extend(item['elements'])
        
        self.report.append("### Global Metrics")
        self.report.append("")
        
        if all_headings:
            self.report.append(f"- **Total Headings Extracted**: {sum(all_headings):,}")
            self.report.append(f"- **Avg Headings per Filing**: {statistics.mean(all_headings):.0f}")
        
        if all_bodies:
            self.report.append(f"- **Total Bodies Extracted**: {sum(all_bodies):,}")
            self.report.append(f"- **Avg Bodies per Filing**: {statistics.mean(all_bodies):.0f}")
        
        if all_headings and all_bodies:
            ratio = sum(all_headings) / sum(all_bodies) if sum(all_bodies) > 0 else 0
            self.report.append(f"- **Overall Heading/Body Ratio**: 1:{ratio:.2f}")
        
        if all_elements:
            self.report.append(f"- **Total Elements**: {sum(all_elements):,}")
            self.report.append(f"- **Avg Elements per Filing**: {statistics.mean(all_elements):.0f}")
        
        self.report.append("")
    
    def _add_item_heatmap(self):
        """Add item statistics heatmap"""
        self.report.append("## 7. Item Statistics Summary")
        self.report.append("")
        
        self.report.append("### Structure Complexity by Item Type")
        self.report.append("")
        self.report.append("| Item | Count | Avg Depth | Avg Headings | Avg Bodies | Avg Elements |")
        self.report.append("|------|-------|-----------|-------------|-----------|--------------|")
        
        for item in sorted(self.stats['items'].keys()):
            item_data = self.stats['items'][item]
            count = item_data['success']
            
            if count > 0:
                avg_depth = statistics.mean(item_data['depths']) if item_data['depths'] else 0
                avg_h = statistics.mean(item_data['headings']) if item_data['headings'] else 0
                avg_b = statistics.mean(item_data['bodies']) if item_data['bodies'] else 0
                avg_e = statistics.mean(item_data['elements']) if item_data['elements'] else 0
                
                self.report.append(f"| Item {item} | {count:,} | {avg_depth:.1f} | {avg_h:.0f} | {avg_b:.0f} | {avg_e:.0f} |")
        
        self.report.append("")
    
    def _add_conclusions(self):
        """Add conclusions section"""
        self.report.append("## 8. Key Insights")
        self.report.append("")
        
        total_filings = sum(sum(v.values()) for v in self.stats['filings'].values())
        
        self.report.append(f"- **Total Filings Analyzed**: {total_filings:,} from {len(self.stats['ciks']):,} companies")
        self.report.append(f"- **Years Covered**: {min(self.stats['years'])}-{max(self.stats['years'])}")
        
        # Find most extracted item
        best_item = max(self.stats['items'].items(), 
                       key=lambda x: x[1]['success'], 
                       default=('Unknown', {'success': 0}))
        
        self.report.append(f"- **Most Extracted Item**: Item {best_item[0]} ({best_item[1]['success']:,} filings)")
        
        # Find deepest structures
        deepest_item = max(self.stats['items'].items(),
                          key=lambda x: max(x[1]['depths']) if x[1]['depths'] else 0,
                          default=('Unknown', {'depths': [0]}))
        
        max_d = max(deepest_item[1]['depths']) if deepest_item[1]['depths'] else 0
        self.report.append(f"- **Most Complex Structure**: Item {deepest_item[0]} (max depth: {max_d})")
        
        self.report.append("")
        self.report.append(f"*Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    def _write_report(self):
        """Write report to file"""
        output_dir = Path('stats')
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f'filing_analysis_{timestamp}.md'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.report))
        
        print(f"\n✅ Report generated: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(
        description='Analyze SEC filings and generate statistics report'
    )
    parser.add_argument(
        '--folder',
        default='sec_filings',
        help='Path to filings folder (default: sec_filings)'
    )
    
    args = parser.parse_args()
    
    try:
        analyzer = FilingAnalyzer(args.folder)
        report_file = analyzer.analyze()
        print(f"\nReport saved to: {report_file}")
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
