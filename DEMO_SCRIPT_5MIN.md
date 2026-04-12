# Ginie Platform - 5-Minute Demo Script

**Total Time: 5-6 minutes**  
**Objective:** Demonstrate the complete AI-powered smart contract lifecycle on Canton Network

---

## 🎯 Demo Flow Overview

1. **Frontend Access & Party Creation** (1 min)
2. **AI-Powered Contract Generation** (1.5 min)
3. **Pipeline Status Tracking** (1.5 min)
4. **Dashboard & Mermaid Visualization** (1 min)
5. **Canton Ledger Explorer & Verification** (1 min)

---

## 📋 Pre-Demo Checklist

- [ ] Canton sandbox running (`start-canton-sandbox.ps1`)
- [ ] Backend running on `http://localhost:8000`
- [ ] Frontend running on `http://localhost:3000`
- [ ] Browser tabs ready: Frontend, Canton Explorer
- [ ] Clear any previous demo data (optional)

---

## 🎬 Demo Script

### **[0:00 - 1:00] Introduction & Party Creation**

**SAY:**  
> "Welcome to Ginie - the AI-powered smart contract platform built on Canton Network. Today I'll show you how we can go from a simple English prompt to a fully deployed, audited, and verified smart contract in under 5 minutes."

**ACTION:**
1. Open browser to `http://localhost:3000`
2. Navigate to the frontend interface

**SAY:**  
> "First, we need to create a party identity on Canton. This is our on-chain identity that will own and interact with contracts."

**ACTION:**
3. Click on **"Create Party"** or navigate to party creation
4. Enter party name: `DemoUser` (or your preferred name)
5. Click **"Create Party"**
6. **SHOW:** Party name appears in the top navigation/header

**SAY:**  
> "Great! Our party is now registered on Canton. You can see our party name here at the top."

---

### **[1:00 - 2:30] AI Contract Generation**

**SAY:**  
> "Now comes the magic. Instead of writing complex Daml code, we'll use natural language to describe what we want."

**ACTION:**
1. Navigate to **"Sandbox"** or **"Generate Contract"** section
2. In the prompt field, enter:
   ```
   Create a simple token contract where users can transfer tokens between parties. Include mint and burn functions with proper authorization.
   ```

**SAY:**  
> "I'm asking Ginie to create a token contract with transfer, mint, and burn capabilities. Let me submit this prompt."

**ACTION:**
3. Click **"Generate & Deploy"** or **"Submit"**
4. **SHOW:** Loading indicator appears

**SAY:**  
> "Behind the scenes, our AI agent is now:
> - Generating the Daml smart contract code
> - Running security audits to check for vulnerabilities
> - Compiling it into a DAR package
> - And deploying it to Canton Network"

---

### **[2:30 - 4:00] Pipeline Status Tracking**

**ACTION:**
1. **SHOW:** Pipeline status view appears automatically or navigate to status page

**SAY:**  
> "Let me walk you through each stage of our automated pipeline:"

**ACTION & EXPLAIN each status as it appears:**

2. **Generation Status** (appears first)
   - **SAY:** "First, the AI generates the Daml contract based on our prompt. You can see the status here."
   - **SHOW:** Status changes to ✅ Complete

3. **Audit Status** (appears next)
   - **SAY:** "Next, our security agent audits the code for common vulnerabilities - things like reentrancy attacks, authorization issues, and logic errors."
   - **SHOW:** Status changes to ✅ Complete

4. **Compilation Status** (appears next)
   - **SAY:** "The code is then compiled into a DAR file - that's Canton's deployment format."
   - **SHOW:** Status changes to ✅ Complete

5. **Deployment Status** (appears last)
   - **SAY:** "Finally, it's deployed to the Canton ledger. And... we're live!"
   - **SHOW:** Status changes to ✅ Complete

---

### **[4:00 - 5:00] Dashboard & Mermaid Visualization**

**ACTION:**
1. Navigate to **"Dashboard"** or **"Pipeline View"**

**SAY:**  
> "Now let's see the complete pipeline visualization."

**ACTION:**
2. **SHOW:** Mermaid diagram displaying the pipeline flow
   - Generation → Audit → Compilation → Deployment

**SAY:**  
> "This Mermaid diagram shows our entire pipeline. Each stage is tracked, and we can see:
> - The deployed contract status
> - All parties involved
> - The complete audit trail"

**ACTION:**
3. Scroll through dashboard showing:
   - Contract details
   - Deployment timestamp
   - Party information
   - Pipeline metrics

---

### **[5:00 - 6:00] Canton Ledger Explorer & Verification**

**SAY:**  
> "Finally, let's verify this on the actual Canton ledger."

**ACTION:**
1. Click **"Open Canton Explorer"** or navigate to Canton Ledger Explorer tab
2. Alternatively, open `http://localhost:7575` (or your Canton console URL)

**SAY:**  
> "Here's the Canton Ledger Explorer - this is the source of truth."

**ACTION:**
3. Navigate to **"Contracts"** or **"Active Contracts"** section
4. **SHOW:** Your deployed contract appears in the list
5. Click on the contract to view details

**SAY:**  
> "You can see our contract is live on the ledger. We can view:
> - The contract template
> - All parties with access
> - The contract arguments and state"

**ACTION:**
6. Navigate to **"Verify Contract"** tab (if available in your frontend)
7. Click **"Verify Contract"**
8. **SHOW:** Verification result appears (✅ Contract verified on ledger)

**SAY:**  
> "And there we have it - verified! Our contract exists on Canton, it's audited, and it's ready for production use."

---

## 🎤 Closing Statement

**SAY:**  
> "So in just 5 minutes, we went from a simple English description to a fully deployed, audited, and verified smart contract on Canton Network. No manual coding, no security oversights, and complete transparency through the entire pipeline. That's the power of Ginie."

**OPTIONAL - Show additional features:**
- "We can also view the generated Daml code if you want to see what the AI created."
- "The audit report is available for review."
- "And we can interact with the contract directly through the explorer."

---

## 🔧 Troubleshooting During Demo

### If Generation Takes Too Long:
**SAY:** "The AI is working on generating optimal code. In production, this typically takes 10-15 seconds."

### If Compilation Fails:
**SAY:** "Looks like we hit a compilation issue. This is rare, but our system will automatically retry with fixes."

### If Canton Explorer Shows No Contracts:
- Refresh the page
- Check party filter is set correctly
- Verify backend logs for deployment confirmation

---

## 📊 Key Metrics to Highlight

- **Time to Deploy:** < 2 minutes from prompt to live contract
- **Security:** Automated audit catches vulnerabilities before deployment
- **Transparency:** Full pipeline visibility and ledger verification
- **Ease of Use:** Natural language → Production-ready contract

---

## 🎯 Demo Success Criteria

✅ Party created and visible  
✅ Contract generated from prompt  
✅ All pipeline stages completed (Generation → Audit → Compile → Deploy)  
✅ Dashboard shows Mermaid diagram  
✅ Contract visible in Canton Explorer  
✅ Contract verification successful  

---

## 💡 Pro Tips

1. **Practice the timing** - Run through the demo 2-3 times to get comfortable with the flow
2. **Have backup scenarios** - Prepare 2-3 different prompts in case you want to show variety
3. **Know your audience** - Emphasize security for enterprise, speed for developers, ease-of-use for business users
4. **Keep talking** - During loading times, explain what's happening behind the scenes
5. **Show confidence** - If something breaks, explain it's a live demo and show how the system handles errors

---

## 📝 Alternative Demo Prompts

If you want to show different use cases:

**Supply Chain:**
```
Create a supply chain tracking contract where items can be transferred between parties and each transfer is recorded with a timestamp.
```

**Escrow:**
```
Create an escrow contract where funds are held until both buyer and seller confirm the transaction.
```

**Voting:**
```
Create a voting contract where authorized parties can cast votes and results are tallied automatically.
```

---

**Last Updated:** April 2026  
**Version:** 1.0  
**Tested On:** Canton Sandbox + Ginie Backend v2
