import requests
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import json
import time
import re
from typing import Dict, List, Optional, Tuple
import urllib.parse

class OSINTScraper:
    def __init__(self, first_name: str, last_name: str, phone: str):
        """
        Initialize the scraper with target identifiers.

        Args:
            first_name: Target's first name
            last_name: Target's last name
            phone: Target's phone number (E.164 format recommended)
        """
        self.first_name = first_name.strip()
        self.last_name = last_name.strip()
        self.phone_raw = phone.strip()
        self.full_name = f"{self.first_name} {self.last_name}"

        
        self.phone_parsed = self._parse_phone()
        self.phone_e164 = None
        self.phone_national = None
        self.phone_country_code = None

        if self.phone_parsed:
            self.phone_e164 = phonenumbers.format_number(
                self.phone_parsed, phonenumbers.PhoneNumberFormat.E164
            )
            self.phone_national = phonenumbers.format_number(
                self.phone_parsed, phonenumbers.PhoneNumberFormat.NATIONAL
            )
            self.phone_country_code = self.phone_parsed.country_code

       
        self.results = {
            "name": self.full_name,
            "phone": {
                "raw": self.phone_raw,
                "e164": self.phone_e164,
                "national": self.phone_national,
                "country_code": self.phone_country_code,
            },
            "sources": {},
            "summary": {}
        }

       
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.timeout = 15

    def _parse_phone(self) -> Optional[phonenumbers.PhoneNumber]:
        """Parse and validate phone number."""
        try:
            # Try parsing with default US, but will detect country automatically
            parsed = phonenumbers.parse(self.phone_raw, None)
            if phonenumbers.is_valid_number(parsed):
                return parsed
            else:
                print(f"[!] Warning: {self.phone_raw} is not a valid phone number")
                return None
        except phonenumbers.NumberParseException as e:
            print(f"[!] Phone parse error: {e}")
            return None

    def _safe_request(self, url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """Make a safe HTTP request with error handling."""
        try:
            time.sleep(1)  # Rate limiting to avoid being blocked
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[!] Request failed for {url}: {e}")
            return None

    # ======================== SOURCE SCRAPERS ========================

    def scrape_google_search(self) -> Dict:
        """
        Google search for name + phone number.
        Note: This uses a basic search; for production use Google Custom Search API.
        """
        print(f"[*] Searching Google for {self.full_name} + {self.phone_national or self.phone_raw}...")

        query = f'"{self.full_name}" "{self.phone_national or self.phone_raw}"'
        search_url = "https://www.google.com/search"
        params = {'q': query, 'num': 10}

        response = self._safe_request(search_url, params)
        if not response:
            return {"error": "Failed to fetch Google results"}

        soup = BeautifulSoup(response.text, 'html.parser')

        
        results = []
        for g in soup.find_all('div', class_='g'):
            title_elem = g.find('h3')
            link_elem = g.find('a')
            snippet_elem = g.find('div', class_='IsZvec')

            if title_elem and link_elem:
                title = title_elem.get_text()
                link = link_elem.get('href', '')
                snippet = snippet_elem.get_text() if snippet_elem else ''
                results.append({
                    'title': title,
                    'url': link,
                    'snippet': snippet
                })

        return {
            'query': query,
            'total_results': len(results),
            'results': results[:10]  # Limit to top 10
        }

    def scrape_phone_validation(self) -> Dict:
        """Extract metadata from phone number using phonenumbers library."""
        print(f"[*] Analyzing phone number: {self.phone_e164}...")

        if not self.phone_parsed:
            return {"error": "Invalid phone number"}

       
        carrier_name = carrier.name_for_number(self.phone_parsed, "en")

       
        location = geocoder.description_for_number(self.phone_parsed, "en")

        
        time_zones = timezone.time_zones_for_number(self.phone_parsed)

      
        number_type = {
            0: "FIXED_LINE",
            1: "MOBILE",
            2: "FIXED_LINE_OR_MOBILE",
            3: "TOLL_FREE",
            4: "PREMIUM_RATE",
            5: "SHARED_COST",
            6: "VOIP",
            7: "PERSONAL_NUMBER",
            8: "PAGER",
            9: "UAN",
            10: "VOICEMAIL",
            11: "UNKNOWN"
        }.get(phonenumbers.number_type(self.phone_parsed), "UNKNOWN")

        return {
            'country': location,
            'carrier': carrier_name,
            'time_zones': list(time_zones),
            'number_type': number_type,
            'is_valid': phonenumbers.is_valid_number(self.phone_parsed),
            'is_possible': phonenumbers.is_possible_number(self.phone_parsed),
            'country_code': self.phone_country_code,
            'national_format': self.phone_national,
            'e164_format': self.phone_e164
        }

    def scrape_haveibeenpwned(self) -> Dict:
        """
        Check if phone or associated email has been in data breaches.
        Note: HIBP API requires authentication for email checks.
        This is a simplified version.
        """
        print(f"[*] Checking breach data for {self.phone_e164}...")


        breach_results = {
            'phone_breaches': [],
            'associated_emails': [],
            'breach_count': 0
        }

        

        return {
            'status': 'HIBP API key required for full functionality',
            'message': 'Visit haveibeenpwned.com to check manually',
            'breach_count': 0
        }

    def scrape_social_username_search(self) -> Dict:
        """
        Search for username profiles across social platforms.
        Uses common username patterns: firstname.lastname or firstlast.
        """
        print(f"[*] Searching social platforms for {self.full_name}...")

        usernames = [
            f"{self.first_name.lower()}.{self.last_name.lower()}",
            f"{self.first_name.lower()}{self.last_name.lower()}",
            f"{self.first_name.lower()}_{self.last_name.lower()}",
            f"{self.first_name[:1].lower()}{self.last_name.lower()}",
            f"{self.last_name.lower()}{self.first_name[:1].lower()}"
        ]

        social_platforms = {
            'twitter': 'https://twitter.com/',
            'instagram': 'https://www.instagram.com/',
            'github': 'https://github.com/',
            'linkedin': 'https://www.linkedin.com/in/',
            'reddit': 'https://www.reddit.com/user/',
            'facebook': 'https://www.facebook.com/',
            'youtube': 'https://www.youtube.com/@',
            'tiktok': 'https://www.tiktok.com/@'
        }

        found_profiles = {}

        for platform, base_url in social_platforms.items():
            for username in usernames:
                profile_url = base_url + username
                try:
                    response = self.session.head(profile_url, timeout=5, allow_redirects=True)
                    # If status code is 200, profile exists
                    if response.status_code == 200:
                        if platform not in found_profiles:
                            found_profiles[platform] = []
                        found_profiles[platform].append({
                            'username': username,
                            'url': profile_url
                        })
                        break  # Found one valid username for this platform
                except:
                    continue

                time.sleep(0.5)  # Rate limit

        return found_profiles

    def scrape_numerous_phone_lookup(self) -> Dict:
        """
        Attempt to use free phone lookup services.
        Note: Most are behind paywalls or captchas; this is a lightweight attempt.
        FIXED: Properly handles string encoding for Python 3.14+
        """
        print(f"[*] Attempting free phone lookup for {self.phone_e164}...")

        
        phone_str = str(self.phone_e164) if self.phone_e164 else self.phone_raw
        phone_encoded = urllib.parse.quote(phone_str, safe='')

        
        lookup_sites = [
            f"https://www.spyDialer.com/search?query={phone_encoded}",
            f"https://www.whitepages.com/phone/{phone_encoded}",
            f"https://www.truecaller.com/search/{phone_encoded}",
            f"https://www.phonevalidator.com/index.aspx?phone={phone_encoded}"
        ]

        results = {}
        for site in lookup_sites:
            try:
                response = self._safe_request(site)
                if response and response.status_code == 200:
                    # Basic parsing - most sites require JavaScript rendering
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Look for any text containing the name
                    if self.full_name.lower() in response.text.lower():
                        results[site] = "Potential name match found"
                    else:
                        results[site] = "No name match on front page"
                else:
                    results[site] = "Access restricted or site unreachable"
            except Exception as e:
                results[site] = f"Error: {str(e)}"

        return results

    def scrape_google_dorking(self) -> Dict:
        """
        Basic Google dorks for finding exposed documents.
        """
        print(f"[*] Performing Google dork searches for {self.full_name}...")

        dorks = [
            f'"{self.full_name}" filetype:pdf',
            f'"{self.full_name}" filetype:doc',
            f'"{self.full_name}" filetype:xls',
            f'"{self.full_name}" "resume" OR "CV"',
            f'"{self.phone_national or self.phone_e164}" filetype:pdf'
        ]

        results = {}
        for dork in dorks[:3]:  # Limit to avoid rate limiting
            search_url = "https://www.google.com/search"
            params = {'q': dork, 'num': 5}

            response = self._safe_request(search_url, params)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                links = []
                for g in soup.find_all('div', class_='g'):
                    link = g.find('a')
                    if link:
                        href = link.get('href', '')
                        if href.startswith('/url?q='):
                            href = href.split('/url?q=')[1].split('&')[0]
                        links.append(href)
                results[dork] = links[:3]
            else:
                results[dork] = "Failed to fetch"

        return results

    # ======================== MAIN EXECUTION ========================

    def run_full_scan(self) -> Dict:
        """
        Execute all scraping modules and aggregate results.
        """
        print(f"\n{'='*60}")
        print(f"OSINT SCAN STARTING")
        print(f"Target: {self.full_name} | Phone: {self.phone_national or self.phone_raw}")
        print(f"{'='*60}\n")

        
        self.results['sources']['phone_metadata'] = self.scrape_phone_validation()

        
        self.results['sources']['google_search'] = self.scrape_google_search()

       
        self.results['sources']['social_profiles'] = self.scrape_social_username_search()

       
        self.results['sources']['phone_lookup'] = self.scrape_numerous_phone_lookup()

        
        self.results['sources']['google_dorks'] = self.scrape_google_dorking()

        
        self.results['sources']['breach_data'] = self.scrape_haveibeenpwned()

        
        self._generate_summary()

        return self.results

    def _generate_summary(self):
        """Create a human-readable summary of findings."""
        summary = []

        phone_data = self.results['sources'].get('phone_metadata', {})
        if phone_data and 'error' not in phone_data:
            summary.append(f"✓ Phone is valid: {phone_data.get('e164_format')}")
            summary.append(f"  - Carrier: {phone_data.get('carrier', 'Unknown')}")
            summary.append(f"  - Location: {phone_data.get('country', 'Unknown')}")
            summary.append(f"  - Type: {phone_data.get('number_type', 'Unknown')}")

       
        google_data = self.results['sources'].get('google_search', {})
        total_results = google_data.get('total_results', 0)
        summary.append(f"✓ Google search found {total_results} public references")

        
        social_data = self.results['sources'].get('social_profiles', {})
        found_platforms = [p for p, data in social_data.items() if data]
        if found_platforms:
            summary.append(f"✓ Found profiles on: {', '.join(found_platforms)}")
        else:
            summary.append("✗ No social media profiles found via username search")

        
        lookup_data = self.results['sources'].get('phone_lookup', {})
        matches = [k for k, v in lookup_data.items() if 'match' in str(v).lower()]
        if matches:
            summary.append(f"✓ Possible name matches on: {len(matches)} phone lookup sites")

        self.results['summary'] = {
            'bullet_points': summary,
            'total_sources_checked': len(self.results['sources']),
            'possible_matches_found': len([s for s in summary if '✓' in s])
        }

        print("\n" + "="*60)
        print("SCAN COMPLETE - SUMMARY")
        print("="*60)
        for point in summary:
            print(point)
        print("="*60)

    def export_json(self, filename: str = "osint_results.json"):
        """Export results to a JSON file."""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"[✓] Results exported to {filename}")

    def export_report(self, filename: str = "osint_report.txt"):
        """Export a human-readable text report."""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("OSINT SCAN REPORT\n")
            f.write("="*60 + "\n\n")
            f.write(f"Target: {self.full_name}\n")
            f.write(f"Phone: {self.phone_national or self.phone_raw}\n")
            f.write(f"Phone (E.164): {self.phone_e164}\n\n")

            f.write("FINDINGS:\n")
            f.write("-"*40 + "\n")
            for point in self.results['summary'].get('bullet_points', []):
                f.write(f"{point}\n")

            f.write("\n\nRAW DATA:\n")
            f.write("-"*40 + "\n")
            f.write(json.dumps(self.results['sources'], indent=2, default=str))

        print(f"[✓] Report exported to {filename}")

# ======================== INPUT FUNCTIONS ========================

def get_user_input() -> Tuple[str, str, str]:
    """
    Prompt the user for first name, last name, and phone number.
    Returns a tuple of (first_name, last_name, phone).
    """
    print("\n" + "="*60)
    print("OSINT DATA SCRAPER - INTERACTIVE MODE")
    print("="*60)
    print("\nPlease enter the target information:")
    print("-" * 40)

   
    while True:
        first_name = input("First Name: ").strip()
        if first_name:
            break
        print("[!] First name cannot be empty. Please try again.")

    
    while True:
        last_name = input("Last Name: ").strip()
        if last_name:
            break
        print("[!] Last name cannot be empty. Please try again.")

   
    while True:
        phone = input("Phone Number (E.164 format, e.g., +15551234567): ").strip()
        if not phone:
            print("[!] Phone number cannot be empty. Please try again.")
            continue

      
        try:
            parsed = phonenumbers.parse(phone, None)
            if phonenumbers.is_valid_number(parsed):
                break
            else:
                print("[!] Invalid phone number format. Please use E.164 format (e.g., +15551234567)")
                print("    Example: +1 for US, +44 for UK, +61 for Australia")
                continue
        except phonenumbers.NumberParseException:
            print("[!] Could not parse phone number. Please use E.164 format (e.g., +15551234567)")
            continue

    print("\n" + "-" * 40)
    print(f"✓ Target set: {first_name} {last_name}")
    print(f"✓ Phone: {phone}")
    print("-" * 40 + "\n")

    return first_name, last_name, phone

def get_scan_options() -> Dict:
    """
    Get optional scan configuration from user.
    """
    print("\nScan Options:")
    print("-" * 40)

   
    while True:
        response = input("Run all OSINT modules? (y/n, default: y): ").strip().lower()
        if response in ['y', 'yes', '']:
            return {'all_modules': True}
        elif response in ['n', 'no']:
            return {'all_modules': False}
        else:
            print("[!] Please enter 'y' or 'n'")

    # Future: Add options to select specific modules

# ======================== ENTRY POINT ========================

def main():
    """Main entry point with interactive prompts."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║        OSINT DATA SCRAPER - EDUCATIONAL USE ONLY            ║
    ║                                                             ║
    ║  WARNING: Use only on yourself or with explicit consent.    ║
    ║  Unauthorized scraping violates privacy laws and ToS.       ║
    ║                                                             ║
    ║  This tool will prompt you for:                             ║
    ║  • First Name                                               ║
    ║  • Last Name                                                ║
    ║  • Phone Number (E.164 format)                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    try:
        
        first_name, last_name, phone = get_user_input()

        
        print("\nStarting OSINT scan with the following parameters:")
        print(f"  • Name: {first_name} {last_name}")
        print(f"  • Phone: {phone}")

        while True:
            confirm = input("\nProceed with scan? (y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                break
            elif confirm in ['n', 'no']:
                print("[!] Scan cancelled by user.")
                return
            else:
                print("[!] Please enter 'y' or 'n'")

       
        scraper = OSINTScraper(first_name, last_name, phone)
        results = scraper.run_full_scan()

       
        scraper.export_json()
        scraper.export_report()

        print("\n[✓] OSINT scan complete. Check osint_results.json and osint_report.txt")

        
        while True:
            view = input("\nView the report now? (y/n): ").strip().lower()
            if view in ['y', 'yes']:
                try:
                    with open("osint_report.txt", 'r', encoding='utf-8') as f:
                        print("\n" + "="*60)
                        print("REPORT CONTENTS")
                        print("="*60)
                        print(f.read())
                        print("="*60)
                except FileNotFoundError:
                    print("[!] Report file not found.")
                break
            elif view in ['n', 'no']:
                break
            else:
                print("[!] Please enter 'y' or 'n'")

        return results

    except KeyboardInterrupt:
        print("\n\n[!] Scan interrupted by user. Exiting...")
        return None
    except Exception as e:
        print(f"\n[!] An unexpected error occurred: {e}")
        return None

if __name__ == "__main__":
    main()
