# OpenAI API Cost Analysis - Contract Generation Pipeline

## Current Configuration
- **Provider**: OpenAI
- **Model**: `gpt-4o` (GPT-4 Optimized)
- **Temperature**: 0.1
- **Timeout**: 90 seconds per request

## LLM Calls Per Contract Generation

### Successful Path (No Compilation Errors)
1. **Intent Agent** - 1 call
   - Max tokens: 1,024
   - Purpose: Parse user input into structured intent

2. **Spec Synthesis** - 1 call
   - Max tokens: 2,048
   - Purpose: Generate structured contract specification/plan

3. **Writer Agent** - 1 call (up to 2 retries)
   - Max tokens: 4,096
   - Purpose: Generate DAML contract code

4. **Security Audit** - 1 call (up to 2 attempts)
   - Max tokens: 8,192
   - Purpose: Deep security analysis with DSV/SWC/OWASP/CWE checks

5. **Compliance Engine** - 1 call (up to 2 attempts)
   - Max tokens: 8,192
   - Purpose: Compliance assessment against industry frameworks

**Minimum calls per successful contract: 5 LLM calls**
**Total output tokens requested: ~23,552 tokens**

### With Compilation Errors (Fix Loop)
6. **Fix Agent** - 1-3 calls (max 3 attempts)
   - Max tokens: 4,096 per attempt
   - Purpose: Auto-fix compilation errors

**With fixes: 6-8 LLM calls**

### Project Mode (Multi-Template)
7. **Project Writer - Types Module** - 1 call
   - Max tokens: 1,024
   - Purpose: Generate shared types module

8. **Project Writer - Per Template** - 1+ calls
   - Max tokens: 4,096 per template
   - Purpose: Generate each template file

**Project mode adds: 2-5 additional calls**

### Optional/Conditional
9. **Test Writer Agent** - 1 call (if enabled)
   - Max tokens: 2,048
   - Purpose: Generate DAML test scenarios

## Cost Estimation (GPT-4o Pricing)

### Current GPT-4o Pricing (as of 2024)
- **Input**: $2.50 per 1M tokens
- **Output**: $10.00 per 1M tokens

### Per Contract Cost Breakdown

#### Minimum Path (No Errors, Single Template)
Assuming average input prompt sizes:
- Intent: ~500 input + 1,024 output
- Spec: ~1,500 input + 2,048 output
- Writer: ~3,000 input + 4,096 output
- Security Audit: ~4,000 input + 8,192 output
- Compliance: ~4,000 input + 8,192 output

**Estimated tokens per contract:**
- Input: ~13,000 tokens
- Output: ~23,552 tokens

**Cost per contract:**
- Input: 13,000 × $2.50 / 1M = $0.0325
- Output: 23,552 × $10.00 / 1M = $0.2355
- **Total: ~$0.27 per contract**

#### With Fix Loop (1-3 fix attempts)
Each fix attempt adds:
- Input: ~4,500 tokens (code + errors)
- Output: ~4,096 tokens

**Additional cost per fix attempt: ~$0.05**
**Total with 3 fixes: ~$0.42 per contract**

#### Project Mode (Multi-Template)
Additional 2-5 calls add:
- Input: ~8,000 tokens
- Output: ~10,000 tokens

**Additional cost: ~$0.12**
**Total project mode: ~$0.39-$0.54 per contract**

## Monthly Cost Projections

### Current Limit: 1 Contract Per User
With 100 invite codes and 100% usage:
- **100 contracts × $0.27 = $27.00/month (minimum)**
- **100 contracts × $0.42 = $42.00/month (with fixes)**

### Previous Limit: 5 Contracts Per User
With 100 users generating 5 contracts each:
- **500 contracts × $0.27 = $135.00/month (minimum)**
- **500 contracts × $0.42 = $210.00/month (with fixes)**

## Cost Optimization Recommendations

### 1. Switch to GPT-4o-mini
- **Input**: $0.15 per 1M tokens (94% cheaper)
- **Output**: $0.60 per 1M tokens (94% cheaper)
- **Per contract cost: ~$0.016** (94% reduction)
- **Trade-off**: Slightly lower quality, may need more fix attempts

### 2. Reduce Audit Scope
- Make security audit optional or user-triggered
- Run compliance only on MainNet deploys
- **Savings: ~$0.16 per contract** (60% reduction)

### 3. Cache/Reuse Patterns
- Cache common contract patterns
- Reuse spec synthesis for similar requests
- **Savings: ~$0.05 per contract** (18% reduction)

### 4. Switch to Gemini or Claude
Already supported in codebase:
- **Gemini 1.5 Flash**: $0.075/$0.30 per 1M tokens (~85% cheaper)
- **Claude 3.5 Haiku**: $0.80/$4.00 per 1M tokens (~60% cheaper)

### 5. Reduce max_tokens Limits
Current limits are generous; actual usage is typically 50-70%:
- Reduce audit tokens: 8,192 → 6,000
- Reduce writer tokens: 4,096 → 3,000
- **Savings: ~$0.08 per contract** (30% reduction)

## Recommended Action Plan

### Immediate (No Code Changes)
1. ✅ **Reduce contract limit to 1 per user** (DONE)
   - Reduces monthly cost from $210 to $42 (80% savings)

### Short-term (Config Changes Only)
2. **Switch to GPT-4o-mini**
   - Set `LLM_MODEL=gpt-4o-mini` in Railway environment
   - Reduces cost to ~$2.50/month for 100 contracts
   - Test quality with 5-10 contracts first

3. **Switch to Gemini 1.5 Flash**
   - Set `LLM_PROVIDER=gemini` and `LLM_MODEL=gemini-1.5-flash`
   - Reduces cost to ~$4/month for 100 contracts
   - Already implemented in codebase

### Medium-term (Code Changes)
4. **Make audit optional**
   - Add user toggle for security audit
   - Run compliance only for MainNet
   - Implement in frontend + backend

5. **Optimize token limits**
   - Reduce max_tokens across all agents
   - Add token usage tracking/logging

## Current Status
- ✅ Contract limit reduced to 1 per user
- ⏳ Model: Still using expensive `gpt-4o`
- ⏳ Audit: Runs on every contract (expensive)
- ⏳ No token usage tracking

## Estimated Monthly Cost (Current Setup)
- **100 users × 1 contract × $0.27 = $27/month (best case)**
- **100 users × 1 contract × $0.42 = $42/month (with fixes)**

## Estimated Monthly Cost (After Optimization)
- **Switch to gpt-4o-mini: $2.50/month**
- **Switch to Gemini Flash: $4.00/month**
- **Make audit optional: $11/month (with gpt-4o)**
