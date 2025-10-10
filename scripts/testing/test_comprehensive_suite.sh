#!/bin/bash

# Comprehensive RAG Service Test Suite
# Run this script to replicate all tests performed in the assessment
# Usage: ./test_comprehensive_suite.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to print test status
print_test() {
    local status=$1
    local name=$2
    local details=$3

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC} - $name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    elif [ "$status" = "FAIL" ]; then
        echo -e "${RED}❌ FAIL${NC} - $name"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    elif [ "$status" = "WARN" ]; then
        echo -e "${YELLOW}⚠️  WARN${NC} - $name"
    else
        echo -e "${BLUE}ℹ️  INFO${NC} - $name"
    fi

    if [ -n "$details" ]; then
        echo "    $details"
    fi
}

# Function to check HTTP response
check_http() {
    local url=$1
    local expected_status=${2:-200}
    local timeout=${3:-10}

    local status=$(curl -s -o /dev/null -w "%{http_code}" --max-time $timeout "$url" 2>/dev/null || echo "000")

    if [ "$status" = "$expected_status" ]; then
        return 0
    else
        return 1
    fi
}

# Function to measure response time
measure_time() {
    local start=$(date +%s%N)
    "$@" > /dev/null 2>&1
    local end=$(date +%s%N)
    local duration=$(( (end - start) / 1000000 )) # Convert to milliseconds
    echo $duration
}

echo "🧪 RAG Service Comprehensive Test Suite"
echo "======================================="
echo

# Test 1: Service Health Check
echo "📊 Testing Service Health..."
if check_http "http://localhost:8001/health"; then
    response=$(curl -s http://localhost:8001/health)
    if echo "$response" | grep -q "healthy"; then
        print_test "PASS" "RAG Service Health" "Service reports healthy status"
    else
        print_test "FAIL" "RAG Service Health" "Service not healthy: $response"
    fi
else
    print_test "FAIL" "RAG Service Health" "Service not accessible on port 8001"
fi

# Test 2: ChromaDB Health
if check_http "http://localhost:8000/api/v2/heartbeat" 200; then
    print_test "PASS" "ChromaDB Health" "ChromaDB v2 API healthy"
else
    print_test "FAIL" "ChromaDB Health" "ChromaDB not accessible or unexpected response"
fi

# Test 3: Baseline Statistics
echo
echo "📈 Checking Baseline Statistics..."
if check_http "http://localhost:8001/stats"; then
    stats=$(curl -s http://localhost:8001/stats)
    doc_count=$(echo "$stats" | grep -o '"total_documents":[0-9]*' | cut -d':' -f2)
    print_test "INFO" "Document Count" "Total documents: $doc_count"

    if [ "$doc_count" -gt 50 ]; then
        print_test "WARN" "Document Count" "High document count suggests duplicates ($doc_count docs)"
    fi
else
    print_test "FAIL" "Stats Endpoint" "Cannot retrieve statistics"
fi

# Test 4: Document Ingestion
echo
echo "📄 Testing Document Ingestion..."

# Create test document
test_content="Test document for comprehensive testing. This contains machine learning concepts, algorithms, and performance metrics."

# Test text document ingestion
start_time=$(date +%s%N)
response=$(curl -s -X POST "http://localhost:8001/ingest" \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"$test_content\", \"filename\": \"test_suite_doc.txt\", \"document_type\": \"text\", \"generate_obsidian\": true}")
end_time=$(date +%s%N)
ingestion_time=$(( (end_time - start_time) / 1000000 ))

if echo "$response" | grep -q "success.*true"; then
    print_test "PASS" "Text Document Ingestion" "Processed in ${ingestion_time}ms"
    doc_id=$(echo "$response" | grep -o '"doc_id":"[^"]*"' | cut -d'"' -f4)
else
    print_test "FAIL" "Text Document Ingestion" "Failed to ingest document"
fi

# Test 5: Search Performance
echo
echo "🔍 Testing Search Performance..."

for query in "machine learning" "algorithms performance" "test document"; do
    start_time=$(date +%s%N)
    search_response=$(curl -s -X POST "http://localhost:8001/search" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"$query\", \"top_k\": 5}")
    end_time=$(date +%s%N)
    search_time=$(( (end_time - start_time) / 1000000 ))

    if echo "$search_response" | grep -q "results"; then
        result_count=$(echo "$search_response" | grep -o '"total_results":[0-9]*' | cut -d':' -f2)
        print_test "PASS" "Search: '$query'" "Found $result_count results in ${search_time}ms"

        if [ "$search_time" -gt 500 ]; then
            print_test "WARN" "Search Performance" "Slow response time: ${search_time}ms"
        fi
    else
        print_test "FAIL" "Search: '$query'" "Search failed or returned no results"
    fi
done

# Test 6: RAG Chat
echo
echo "💬 Testing RAG Chat..."
start_time=$(date +%s%N)
chat_response=$(curl -s -X POST "http://localhost:8001/chat" \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"What machine learning concepts are mentioned in the documents?\", \"max_context_chunks\": 3, \"include_sources\": true}")
end_time=$(date +%s%N)
chat_time=$(( (end_time - start_time) / 1000000 ))

if echo "$chat_response" | grep -q "answer"; then
    print_test "PASS" "RAG Chat Response" "Generated response in ${chat_time}ms"

    if echo "$chat_response" | grep -q "sources"; then
        print_test "PASS" "RAG Source Attribution" "Sources included in response"
    else
        print_test "WARN" "RAG Source Attribution" "No sources in response"
    fi
else
    print_test "FAIL" "RAG Chat Response" "Failed to generate chat response"
fi

# Test 7: LLM Provider Testing
echo
echo "🤖 Testing LLM Providers..."

for provider in "groq" "anthropic" "openai"; do
    llm_response=$(curl -s -X POST "http://localhost:8001/test-llm" \
        -H "Content-Type: application/json" \
        -d "{\"provider\": \"$provider\", \"prompt\": \"Test prompt\"}")

    if echo "$llm_response" | grep -q "success.*true"; then
        print_test "PASS" "LLM Provider: $provider" "Provider functional"
    else
        error_msg=$(echo "$llm_response" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
        print_test "FAIL" "LLM Provider: $provider" "Error: $error_msg"
    fi
done

# Test 8: Error Handling
echo
echo "⚠️  Testing Error Handling..."

# Test empty document
empty_response=$(curl -s -X POST "http://localhost:8001/ingest" \
    -H "Content-Type: application/json" \
    -d '{"content": "", "filename": "empty.txt"}')

if echo "$empty_response" | grep -q "500\|error"; then
    print_test "FAIL" "Empty Document Handling" "Should reject gracefully, not 500 error"
else
    print_test "PASS" "Empty Document Handling" "Handled gracefully"
fi

# Test empty search query
empty_search=$(curl -s -X POST "http://localhost:8001/search" \
    -H "Content-Type: application/json" \
    -d '{"text": "", "top_k": 5}')

if echo "$empty_search" | grep -q "results"; then
    print_test "WARN" "Empty Search Query" "Should reject empty queries"
else
    print_test "PASS" "Empty Search Query" "Properly rejected"
fi

# Test 9: Resource Usage
echo
echo "💾 Testing Resource Usage..."
if command -v docker &> /dev/null; then
    docker_stats=$(docker stats rag_service rag_chromadb --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}" | tail -n +2)

    rag_mem=$(echo "$docker_stats" | grep rag_service | awk '{print $2}' | cut -d'/' -f1)
    chroma_mem=$(echo "$docker_stats" | grep rag_chromadb | awk '{print $2}' | cut -d'/' -f1)

    print_test "INFO" "Resource Usage" "RAG: $rag_mem, ChromaDB: $chroma_mem"

    # Check if memory usage is reasonable (under 500MB for RAG service)
    rag_mem_mb=$(echo "$rag_mem" | sed 's/MiB//' | cut -d'.' -f1)
    if [ "$rag_mem_mb" -lt 500 ]; then
        print_test "PASS" "Memory Usage" "RAG service using reasonable memory ($rag_mem)"
    else
        print_test "WARN" "Memory Usage" "RAG service using high memory ($rag_mem)"
    fi
else
    print_test "WARN" "Resource Usage" "Docker not available for resource testing"
fi

# Test 10: Cost Tracking
echo
echo "💰 Testing Cost Tracking..."
if check_http "http://localhost:8001/cost-stats"; then
    cost_stats=$(curl -s http://localhost:8001/cost-stats)
    total_cost=$(echo "$cost_stats" | grep -o '"total_cost_today":[0-9.]*' | cut -d':' -f2)
    print_test "PASS" "Cost Tracking" "Total cost today: \$$total_cost"
else
    print_test "FAIL" "Cost Tracking" "Cost stats endpoint not accessible"
fi

# Test 11: Document Deduplication Check
echo
echo "🔄 Testing Document Deduplication..."
if check_http "http://localhost:8001/documents"; then
    docs=$(curl -s "http://localhost:8001/documents")
    advanced_ml_count=$(echo "$docs" | grep -o "advanced_ml.md" | wc -l)

    if [ "$advanced_ml_count" -gt 5 ]; then
        print_test "FAIL" "Document Deduplication" "Found $advanced_ml_count copies of advanced_ml.md"
    else
        print_test "PASS" "Document Deduplication" "No obvious duplicates detected"
    fi
else
    print_test "FAIL" "Document Listing" "Cannot retrieve document list"
fi

# Test Summary
echo
echo "📊 Test Summary"
echo "==============="
echo -e "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo -e "Warnings: $((TOTAL_TESTS - PASSED_TESTS - FAILED_TESTS))"

# Calculate pass rate
if [ $TOTAL_TESTS -gt 0 ]; then
    pass_rate=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
    echo -e "Pass Rate: $pass_rate%"

    if [ $pass_rate -ge 80 ]; then
        echo -e "${GREEN}🎉 Overall Status: GOOD${NC}"
    elif [ $pass_rate -ge 60 ]; then
        echo -e "${YELLOW}⚠️  Overall Status: NEEDS IMPROVEMENT${NC}"
    else
        echo -e "${RED}❌ Overall Status: CRITICAL ISSUES${NC}"
    fi
fi

echo
echo "For detailed analysis, see: COMPREHENSIVE_TEST_REPORT_2025-09-27.md"

# Exit with error code if any tests failed
if [ $FAILED_TESTS -gt 0 ]; then
    exit 1
fi

exit 0