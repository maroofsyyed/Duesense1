#!/usr/bin/env python3
"""Simple tests for Website Due Diligence Scoring"""

def test_website_dd_scoring_with_no_pricing():
    """Test: Website with no pricing page should get pricing score = 0"""
    from services.scorer import _agent_website_due_diligence
    import asyncio
    
    # Mock website DD data with no pricing
    mock_dd_data = {
        "status": "completed",
        "pages_crawled": 5,
        "extraction": {
            "product_signals": {
                "product_description": "Great product [SOURCE: /]",
                "key_features": ["Feature 1 [SOURCE: /features]"],
                "api_available": "true"
            },
            "business_model_signals": {
                "pricing_model": "not_mentioned",
                "price_points": [],
                "free_trial": "not_mentioned",
                "sales_motion": "not_mentioned"
            },
            "customer_validation_signals": {
                "customer_logos_count": "not_mentioned",
                "case_study_count": "not_mentioned",
                "named_customers": []
            },
            "trust_compliance_signals": {
                "security_page_exists": True,
                "certifications": [],
                "privacy_policy_exists": True
            }
        }
    }
    
    result = asyncio.run(_agent_website_due_diligence(mock_dd_data))
    
    # Assertions
    assert result['breakdown']['pricing_gtm_clarity'] == 0, f"Expected pricing score = 0, got {result['breakdown']['pricing_gtm_clarity']}"
    assert "No clear pricing model" in result['red_flags'], "Expected 'No clear pricing model' in red flags"
    assert "No pricing information" in result['red_flags'], "Expected 'No pricing information' in red flags"
    
    print("✅ Test 1 PASSED: Website with no pricing gets pricing_gtm_clarity score = 0")
    print(f"   Score breakdown: {result['breakdown']}")
    print(f"   Red flags: {result['red_flags']}")
    return True


def test_website_dd_scoring_with_security_page():
    """Test: Website with security page present should get trust score = 1"""
    from services.scorer import _agent_website_due_diligence
    import asyncio
    
    # Mock website DD data with security page
    mock_dd_data = {
        "status": "completed",
        "pages_crawled": 10,
        "extraction": {
            "product_signals": {
                "product_description": "Enterprise security platform [SOURCE: /]",
                "key_features": ["Feature 1 [SOURCE: /]", "Feature 2 [SOURCE: /]"],
                "api_available": "true"
            },
            "business_model_signals": {
                "pricing_model": "subscription",
                "price_points": ["$99/mo [SOURCE: /pricing]"],
                "free_trial": "true",
                "sales_motion": "self_serve"
            },
            "customer_validation_signals": {
                "customer_logos_count": "5",
                "case_study_count": "2",
                "named_customers": ["Customer A [SOURCE: /customers]"]
            },
            "trust_compliance_signals": {
                "security_page_exists": True,
                "certifications": ["SOC2 [SOURCE: /security]", "ISO27001 [SOURCE: /security]"],
                "privacy_policy_exists": True
            }
        }
    }
    
    result = asyncio.run(_agent_website_due_diligence(mock_dd_data))
    
    # Assertions
    assert result['breakdown']['trust_compliance'] == 1.0, f"Expected trust score = 1.0, got {result['breakdown']['trust_compliance']}"
    assert "Security page exists" in result['green_flags'], "Expected 'Security page exists' in green flags"
    assert "Privacy policy exists" in result['green_flags'], "Expected 'Privacy policy exists' in green flags"
    assert result['total_website_dd_score'] > 5, f"Expected total score > 5 for complete website, got {result['total_website_dd_score']}"
    
    print("✅ Test 2 PASSED: Website with security page gets trust_compliance score = 1.0")
    print(f"   Total score: {result['total_website_dd_score']}/10")
    print(f"   Score breakdown: {result['breakdown']}")
    print(f"   Green flags: {result['green_flags']}")
    return True


if __name__ == "__main__":
    import sys
    import os
    
    # Add backend to path and load environment
    sys.path.insert(0, '/app/backend')
    from dotenv import load_dotenv
    load_dotenv('/app/backend/.env')
    
    print("\n" + "="*60)
    print("Website Due Diligence Scoring Tests")
    print("="*60 + "\n")
    
    try:
        # Run tests
        test1_passed = test_website_dd_scoring_with_no_pricing()
        print()
        test2_passed = test_website_dd_scoring_with_security_page()
        
        print("\n" + "="*60)
        if test1_passed and test2_passed:
            print("✅ ALL TESTS PASSED (2/2)")
            print("="*60 + "\n")
            sys.exit(0)
        else:
            print("❌ SOME TESTS FAILED")
            print("="*60 + "\n")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
