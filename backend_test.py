#!/usr/bin/env python3
import requests
import sys
import json
from datetime import datetime

class VCIntelligenceAPITester:
    def __init__(self, base_url="https://38ff65e6-4c92-46cd-aea1-1ff7ca9c46eb.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.test_company_id = "6988bd53ca90ef491b49430b"  # TechVault AI
        
    def print_test(self, name, status, details=""):
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {name}")
        if details:
            print(f"   {details}")
        
    def run_test(self, name, method, endpoint, expected_status=200, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {} if files else {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, timeout=60)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=60)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            
            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                try:
                    resp_data = response.json() if response.content else {}
                    self.print_test(f"Passed - Status: {response.status_code}", True)
                    return True, resp_data
                except json.JSONDecodeError:
                    self.print_test(f"Passed - Status: {response.status_code} (Non-JSON response)", True)
                    return True, {}
            else:
                self.print_test(f"Failed - Expected {expected_status}, got {response.status_code}", False, 
                              f"Response: {response.text[:200]}")
                return False, {}
                
        except Exception as e:
            self.print_test(f"Failed - Error: {str(e)}", False)
            return False, {}

    def test_health_endpoint(self):
        """Test health endpoint"""
        success, response = self.run_test("Health Check", "GET", "api/health", 200)
        return success

    def test_dashboard_stats(self):
        """Test dashboard stats endpoint"""
        success, response = self.run_test("Dashboard Stats", "GET", "api/dashboard/stats", 200)
        if success:
            required_fields = ['total_companies', 'processing', 'completed', 'failed', 'tiers']
            missing_fields = [f for f in required_fields if f not in response]
            if missing_fields:
                self.print_test(f"Missing fields: {missing_fields}", False)
                return False
            else:
                self.print_test(f"All required fields present: {required_fields}", True)
        return success

    def test_list_companies(self):
        """Test listing all companies"""
        success, response = self.run_test("List Companies", "GET", "api/companies", 200)
        if success and 'companies' in response:
            companies = response['companies']
            self.print_test(f"Found {len(companies)} companies", True)
            # Check if test company exists
            test_company = next((c for c in companies if c['id'] == self.test_company_id), None)
            if test_company:
                self.print_test(f"Test company 'TechVault AI' found with ID {self.test_company_id}", True)
                return True, test_company
            else:
                self.print_test("Test company not found in list", False)
                return True, None
        return success, None

    def test_get_company_details(self, company_id=None):
        """Test getting specific company details"""
        test_id = company_id or self.test_company_id
        success, response = self.run_test("Get Company Details", "GET", f"api/companies/{test_id}", 200)
        
        if success:
            required_sections = ['company', 'pitch_decks', 'founders', 'enrichments', 'score', 'competitors', 'memo']
            missing_sections = [s for s in required_sections if s not in response]
            if missing_sections:
                self.print_test(f"Missing sections: {missing_sections}", False)
            else:
                self.print_test("All required sections present", True)
                
                # Check specific data for test company
                if response.get('company', {}).get('name') == 'TechVault AI':
                    self.print_test("Test company name verified", True)
                if response.get('score', {}).get('total_score') == 73:
                    self.print_test("Test company score verified (73)", True)
                if response.get('score', {}).get('tier') == 'TIER_2':
                    self.print_test("Test company tier verified (TIER_2)", True)
        
        return success

    def test_get_company_score(self, company_id=None):
        """Test getting company score"""
        test_id = company_id or self.test_company_id
        success, response = self.run_test("Get Company Score", "GET", f"api/companies/{test_id}/score", 200)
        
        if success:
            required_fields = ['total_score', 'tier', 'founder_score', 'market_score', 'moat_score', 'traction_score', 'model_score']
            missing_fields = [f for f in required_fields if f not in response]
            if missing_fields:
                self.print_test(f"Missing score fields: {missing_fields}", False)
            else:
                self.print_test("All score fields present", True)
        
        return success

    def test_get_company_memo(self, company_id=None):
        """Test getting company memo"""
        test_id = company_id or self.test_company_id
        success, response = self.run_test("Get Company Memo", "GET", f"api/companies/{test_id}/memo", 200)
        
        if success:
            if 'sections' in response:
                sections_count = len(response['sections'])
                self.print_test(f"Memo has {sections_count} sections", True)
            else:
                self.print_test("Memo missing sections", False)
        
        return success

    def test_upload_functionality_check(self):
        """Test if upload endpoint exists (won't actually upload)"""
        # Just test if the endpoint exists by making an invalid request
        print(f"\n🔍 Testing Upload Endpoint Availability...")
        url = f"{self.base_url}/api/decks/upload"
        try:
            # Make request without file to check endpoint exists
            response = requests.post(url, timeout=10)
            # Expect 422 (validation error) since no file provided
            if response.status_code in [422, 400]:
                self.tests_run += 1
                self.tests_passed += 1
                self.print_test("Upload endpoint available (validation error as expected)", True)
                return True
            else:
                self.tests_run += 1
                self.print_test(f"Upload endpoint returned unexpected status: {response.status_code}", False)
                return False
        except Exception as e:
            self.tests_run += 1
            self.print_test(f"Upload endpoint test failed: {str(e)}", False)
            return False

    def test_deck_status_endpoint(self):
        """Test deck status endpoint with known deck ID"""
        # Try with test deck ID from agent context
        test_deck_id = "6988bd53ca90ef491b49430c"
        success, response = self.run_test("Get Deck Status", "GET", f"api/decks/{test_deck_id}/status", 200)
        
        if success:
            status_fields = ['processing_status', 'file_name', 'file_size']
            present_fields = [f for f in status_fields if f in response]
            self.print_test(f"Status fields present: {present_fields}", len(present_fields) > 0)
        
        return success

    def test_nonexistent_company(self):
        """Test getting non-existent company returns 404"""
        fake_id = "000000000000000000000000"
        success, response = self.run_test("Non-existent Company", "GET", f"api/companies/{fake_id}", 404)
        return success

def main():
    print("🚀 Starting VC Deal Intelligence API Tests")
    print("=" * 60)
    
    tester = VCIntelligenceAPITester()
    
    # Run all tests
    tests = [
        tester.test_health_endpoint,
        tester.test_dashboard_stats, 
        tester.test_list_companies,
        tester.test_get_company_details,
        tester.test_get_company_score,
        tester.test_get_company_memo,
        tester.test_upload_functionality_check,
        tester.test_deck_status_endpoint,
        tester.test_nonexistent_company,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {str(e)}")
            results.append(False)
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"📊 TEST SUMMARY")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        failed = tester.tests_run - tester.tests_passed
        print(f"⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())