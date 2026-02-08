#!/usr/bin/env python3
"""Backend API Test Suite for VC Deal Intelligence System with Website Intelligence"""
import requests
import sys
import json
from datetime import datetime
import time

class VCDealAPITester:
    def __init__(self, base_url="https://trust-signal-crawler.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
                try:
                    resp_json = response.json() if response.content else {}
                    if resp_json:
                        print(f"   Response Preview: {json.dumps(resp_json, default=str)[:200]}...")
                except:
                    print(f"   Response Content: {response.text[:200]}...")
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                print(f"   Error: {response.text[:500]}")
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "error": response.text[:500]
                })

            return success, response

        except requests.Timeout:
            print(f"❌ FAILED - Request timed out after {timeout}s")
            self.failed_tests.append({
                "test": name,
                "error": f"Request timeout after {timeout}s"
            })
            return False, None
        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            self.failed_tests.append({
                "test": name,
                "error": str(e)
            })
            return False, None

    def test_health_check(self):
        """Test health endpoint"""
        success, response = self.run_test("Health Check", "GET", "api/health", 200)
        return success

    def test_dashboard_stats(self):
        """Test dashboard stats endpoint"""
        success, response = self.run_test("Dashboard Stats", "GET", "api/dashboard/stats", 200)
        if success and response:
            try:
                data = response.json()
                print(f"   📊 Total Companies: {data.get('total_companies', 'N/A')}")
                print(f"   📊 Completed: {data.get('completed', 'N/A')}")
                print(f"   📊 Processing: {data.get('processing', 'N/A')}")
                recent = data.get('recent_companies', [])
                if recent:
                    print(f"   📊 Recent companies: {len(recent)} found")
                    for comp in recent[:3]:  # Show first 3
                        print(f"      - {comp.get('name', 'Unknown')} ({comp.get('status', 'unknown')})")
            except:
                pass
        return success

    def test_companies_list(self):
        """Test companies list endpoint"""
        success, response = self.run_test("List All Companies", "GET", "api/companies", 200)
        if success and response:
            try:
                data = response.json()
                companies = data.get('companies', [])
                print(f"   📋 Found {len(companies)} companies")
                # Find TechVault AI
                techvault = None
                for c in companies:
                    if 'techvault' in c.get('name', '').lower():
                        techvault = c
                        break
                if techvault:
                    print(f"   ✅ Found TechVault AI: {techvault.get('id')}")
                    return success, techvault
                else:
                    print(f"   ⚠️  TechVault AI not found in companies list")
            except Exception as e:
                print(f"   Error parsing companies: {e}")
        return success, None

    def test_company_detail(self, company_id):
        """Test specific company detail endpoint"""
        if not company_id:
            print("❌ No company ID provided for detail test")
            return False
        
        success, response = self.run_test(
            f"Company Detail ({company_id})", 
            "GET", 
            f"api/companies/{company_id}", 
            200,
            timeout=60
        )
        
        if success and response:
            try:
                data = response.json()
                company = data.get('company', {})
                print(f"   🏢 Company: {company.get('name', 'N/A')}")
                print(f"   📊 Status: {company.get('status', 'N/A')}")
                print(f"   🌐 Website: {company.get('website', 'N/A')}")
                
                # Check if enrichments include website_intelligence
                enrichments = data.get('enrichments', [])
                wi_found = any(e.get('source_type') == 'website_intelligence' for e in enrichments)
                print(f"   🔍 Website Intelligence: {'✅ Found' if wi_found else '❌ Missing'}")
                
                # Check score data
                score = data.get('score', {})
                if score:
                    print(f"   🎯 Score: {score.get('total_score', 'N/A')}/{score.get('tier', 'N/A')}")
                    print(f"   🌐 Website Score: {score.get('website_score', 'N/A')}/10")
                
                return success, data
            except Exception as e:
                print(f"   Error parsing company detail: {e}")
        
        return success, None

    def test_company_score(self, company_id):
        """Test company score endpoint"""
        if not company_id:
            print("❌ No company ID provided for score test")
            return False
        
        success, response = self.run_test(
            f"Company Score ({company_id})", 
            "GET", 
            f"api/companies/{company_id}/score", 
            200
        )
        
        if success and response:
            try:
                data = response.json()
                print(f"   🎯 Total Score: {data.get('total_score', 'N/A')}")
                print(f"   🏆 Tier: {data.get('tier', 'N/A')}")
                print(f"   👥 Founder Score: {data.get('founder_score', 'N/A')}/25")
                print(f"   📈 Market Score: {data.get('market_score', 'N/A')}/20")
                print(f"   🔒 Moat Score: {data.get('moat_score', 'N/A')}/20")
                print(f"   📊 Traction Score: {data.get('traction_score', 'N/A')}/15")
                print(f"   💼 Model Score: {data.get('model_score', 'N/A')}/10")
                print(f"   🌐 Website Score: {data.get('website_score', 'N/A')}/10")
                
                # Check if we have 6 scoring dimensions
                weights = data.get('scoring_weights', {})
                if len(weights) == 6 and 'website_intelligence' in weights:
                    print("   ✅ All 6 scoring dimensions present including Website Intelligence")
                else:
                    print("   ❌ Missing or incorrect scoring dimensions")
                
            except Exception as e:
                print(f"   Error parsing score data: {e}")
        
        return success

    def test_website_intelligence(self, company_id):
        """Test website intelligence endpoint"""
        if not company_id:
            print("❌ No company ID provided for website intelligence test")
            return False
        
        success, response = self.run_test(
            f"Website Intelligence ({company_id})", 
            "GET", 
            f"api/companies/{company_id}/website-intelligence", 
            200,
            timeout=60
        )
        
        if success and response:
            try:
                data = response.json()
                print(f"   🔍 Website Intelligence Data Available")
                
                # Check for key intelligence components
                intelligence_summary = data.get('intelligence_summary', {})
                if intelligence_summary:
                    overall_score = intelligence_summary.get('overall_score', 0)
                    print(f"   📊 Overall Website Score: {overall_score}/100")
                    
                    # Check for score breakdown
                    breakdown = intelligence_summary.get('score_breakdown', {})
                    if breakdown:
                        print("   📈 Score Breakdown:")
                        for metric, score in breakdown.items():
                            print(f"      - {metric}: {score}/20")
                    
                    # Check flags
                    green_flags = intelligence_summary.get('green_flags', [])
                    red_flags = intelligence_summary.get('red_flags', [])
                    print(f"   ✅ Green Flags: {len(green_flags)}")
                    print(f"   ❌ Red Flags: {len(red_flags)}")
                
                # Check crawl metadata
                crawl_meta = data.get('crawl_meta', {})
                if crawl_meta:
                    pages_crawled = crawl_meta.get('pages_crawled', 0)
                    pages_attempted = crawl_meta.get('pages_attempted', 0)
                    print(f"   🕸️ Pages Crawled: {pages_crawled}/{pages_attempted}")
                
                # Check for 7 AI agent outputs
                agent_outputs = [
                    'product_intel', 'revenue_model', 'customer_validation', 
                    'team_intel', 'technical_depth', 'traction_signals', 'compliance'
                ]
                found_agents = [agent for agent in agent_outputs if agent in data]
                print(f"   🤖 AI Agents Found: {len(found_agents)}/7 ({', '.join(found_agents)})")
                
                # Check tech stack and sales signals
                tech_stack = data.get('tech_stack', {})
                sales_signals = data.get('sales_signals', {})
                print(f"   💻 Tech Stack: {'✅ Present' if tech_stack else '❌ Missing'}")
                print(f"   💰 Sales Signals: {'✅ Present' if sales_signals else '❌ Missing'}")
                
            except Exception as e:
                print(f"   Error parsing website intelligence: {e}")
        
        return success

    def test_upload_endpoint(self):
        """Test upload endpoint (POST structure only - no actual file)"""
        # Test with no file to verify endpoint structure
        success, response = self.run_test(
            "Upload Endpoint Structure", 
            "POST", 
            "api/decks/upload", 
            422  # Expected validation error for missing file
        )
        
        if response and response.status_code == 422:
            print("   ✅ Upload endpoint properly validates file requirement")
            return True
        return success

def main():
    print("🚀 Starting VC Deal Intelligence API Testing Suite")
    print("=" * 80)
    
    tester = VCDealAPITester()
    
    # Core API tests
    if not tester.test_health_check():
        print("❌ Health check failed - stopping tests")
        return 1
    
    print("\n" + "=" * 50)
    print("📊 Testing Dashboard & Companies")
    
    if not tester.test_dashboard_stats():
        print("❌ Dashboard stats failed")
    
    companies_success, techvault_company = tester.test_companies_list()
    if not companies_success:
        print("❌ Companies list failed")
    
    # Test upload endpoint structure
    tester.test_upload_endpoint()
    
    # Test specific company (TechVault AI or first available)
    test_company_id = None
    if techvault_company:
        test_company_id = techvault_company.get('id')
        print(f"\n🎯 Using TechVault AI for detailed testing: {test_company_id}")
    else:
        # Try the provided test ID from context
        test_company_id = "6988c1d18f24363888950397"
        print(f"\n🎯 Using provided test company ID: {test_company_id}")
    
    if test_company_id:
        print("\n" + "=" * 50)
        print(f"🏢 Testing Company Detail Features")
        
        # Company detail test
        company_success, company_data = tester.test_company_detail(test_company_id)
        
        # Score endpoint test
        tester.test_company_score(test_company_id)
        
        # Website intelligence test
        tester.test_website_intelligence(test_company_id)
    
    # Print final results
    print("\n" + "=" * 80)
    print("📋 TEST SUMMARY")
    print("=" * 80)
    print(f"🎯 Tests Run: {tester.tests_run}")
    print(f"✅ Tests Passed: {tester.tests_passed}")
    print(f"❌ Tests Failed: {len(tester.failed_tests)}")
    print(f"📊 Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if tester.failed_tests:
        print("\n❌ FAILED TESTS:")
        for i, failure in enumerate(tester.failed_tests, 1):
            print(f"{i}. {failure['test']}")
            if 'expected' in failure:
                print(f"   Expected: {failure['expected']}, Got: {failure['actual']}")
            print(f"   Error: {failure['error'][:200]}...")
    
    return 0 if len(tester.failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())