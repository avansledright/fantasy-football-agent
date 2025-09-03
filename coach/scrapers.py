import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

class FantasyProjectionScraper:
    """Handles scraping current week projections"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.position_urls = {
            'QB': 'qb', 'RB': 'rb', 'WR': 'wr', 'TE': 'te', 'K': 'k', 'DST': 'dst'
        }
        
    def scrape_all_projections(self, week: int) -> Dict[str, Dict[str, float]]:
        """Scrape current week projections for all positions"""
        all_projections = {}
        
        for position, url_suffix in self.position_urls.items():
            try:
                url = f"https://www.fantasypros.com/nfl/projections/{url_suffix}.php?week={week}"
                logger.info(f"Scraping {position} projections from: {url}")
                
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
                
                if not table:
                    logger.warning(f"No projection table found for {position}")
                    continue
                
                projections = self._parse_projection_table(table)
                all_projections[position] = projections
                logger.info(f"Scraped {len(projections)} {position} projections")
                
                time.sleep(1.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error scraping {position} projections: {str(e)}")
                all_projections[position] = {}
        
        return all_projections
    
    def scrape_injury_report(self) -> Dict[str, str]:
        """Scrape current injury report"""
        injuries = {}
        
        try:
            url = "https://www.fantasypros.com/nfl/injury-report.php"
            logger.info(f"Scraping injury report from: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
            
            if table:
                tbody = table.find('tbody')
                if tbody:
                    for row in tbody.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            player_name = self._extract_player_name(cells[0])
                            
                            # Get injury status
                            status = "Healthy"
                            for cell in cells[-3:]:
                                cell_text = cell.get_text(strip=True)
                                if cell_text in ['Out', 'Doubtful', 'Questionable', 'Probable']:
                                    status = cell_text
                                    break
                            
                            injuries[player_name] = status
            
            logger.info(f"Scraped injury status for {len(injuries)} players")
            
        except Exception as e:
            logger.error(f"Error scraping injury report: {str(e)}")
            
        return injuries
    
    def _parse_projection_table(self, table) -> Dict[str, float]:
        """Parse projection table and return player:points mapping"""
        projections = {}
        
        # Get headers
        headers = []
        header_row = table.find('thead')
        if header_row:
            for th in header_row.find('tr').find_all('th'):
                headers.append(th.get_text(strip=True))
        
        # Find fantasy points column
        fpts_col = None
        for i, header in enumerate(headers):
            if any(keyword in header.lower() for keyword in ['fpts', 'fantasy', 'points']):
                fpts_col = i
                break
        
        if fpts_col is None:
            fpts_col = len(headers) - 1  # Use last column as fallback
        
        # Parse data rows
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) > fpts_col:
                    player_name = self._extract_player_name(cells[0])
                    
                    try:
                        fpts_text = cells[fpts_col].get_text(strip=True)
                        fpts = float(fpts_text) if fpts_text.replace('.', '').replace('-', '').isdigit() else 0.0
                        projections[player_name] = fpts
                    except (ValueError, IndexError):
                        continue
        
        return projections
    
    def _extract_player_name(self, cell) -> str:
        """Extract and clean player name from table cell"""
        player_link = cell.find('a')
        if player_link:
            player_name = player_link.get_text(strip=True)
        else:
            player_name = cell.get_text(strip=True)
        
        # Clean name
        player_name = re.sub(r'\s+[A-Z]{2,3}$', '', player_name)  # Remove team abbreviation
        player_name = re.sub(r'\s+\([^)]+\)', '', player_name)    # Remove parenthetical info
        
        return player_name