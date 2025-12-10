# Part 4: Next.js Frontend

**Parallel Execution Group**: Can run completely in parallel with Parts 1-3
**Dependencies**: Part 3 (API endpoints) for integration testing
**Estimated Effort**: 4-5 hours

---

## Scope

This part implements the Next.js frontend dashboard:
1. Project setup with Tailwind + shadcn/ui
2. File upload component
3. Analysis dashboard page
4. Risk visualization components
5. Chat interface for Q&A
6. Cost dashboard

---

## Task 4.1: Project Setup

**Directory**: `frontend/`

### Requirements
- Next.js 14+ with App Router
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Axios for API calls

### Commands
```bash
npx create-next-app@latest frontend --typescript --tailwind --app --src-dir --import-alias "@/*"
cd frontend
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input textarea badge progress tabs
npm install axios recharts lucide-react
```

### Success Criteria
- [ ] Next.js dev server starts
- [ ] Tailwind styles work
- [ ] shadcn/ui components available

---

## Task 4.2: API Client

**File**: `frontend/src/lib/api.ts`

### Requirements
- Axios instance with base URL from env
- Functions for:
  - `uploadContract(file: File)` - POST /api/contracts/upload
  - `queryContract(contractId: string, query: string)` - POST /api/contracts/{id}/query
  - `getContractDetails(contractId: string)` - GET /api/contracts/{id}
  - `getCostAnalytics(date?: string)` - GET /api/analytics/costs
- TypeScript types for all responses

### Success Criteria
- [ ] All API functions typed
- [ ] Error handling works
- [ ] Base URL configurable

---

## Task 4.3: File Upload Component

**File**: `frontend/src/components/FileUpload.tsx`

### Requirements
- Drag-and-drop zone
- File type validation (PDF only)
- Upload progress indicator
- Success/error states
- Callback on successful upload with contract_id

### Success Criteria
- [ ] Drag-and-drop works
- [ ] Shows upload progress
- [ ] Validates PDF files
- [ ] Returns contract_id on success

---

## Task 4.4: Home Page (Upload)

**File**: `frontend/src/app/page.tsx`

### Requirements
- Clean upload interface
- FileUpload component
- Redirect to dashboard on success
- Recent contracts list (optional)

### Success Criteria
- [ ] Upload flow works end-to-end
- [ ] Navigates to dashboard after upload

---

## Task 4.5: Dashboard Page

**File**: `frontend/src/app/dashboard/[contractId]/page.tsx`

### Requirements
- Dynamic route with contractId param
- Fetch contract details on mount
- Tab-based layout:
  - Summary tab
  - Risk Analysis tab
  - Chat tab
- Loading and error states

### Success Criteria
- [ ] Loads contract data
- [ ] Tabs switch correctly
- [ ] Error handling works

---

## Task 4.6: Contract Summary Component

**File**: `frontend/src/components/ContractSummary.tsx`

### Requirements
- Display:
  - Contract metadata (filename, date, parties)
  - Key terms (payment, termination, liability)
  - Risk score badge (color-coded)
- Clean card layout

### Success Criteria
- [ ] Displays all metadata
- [ ] Risk badge color-coded (green/yellow/red)
- [ ] Responsive design

---

## Task 4.7: Risk Heatmap Component

**File**: `frontend/src/components/RiskHeatmap.tsx`

### Requirements
- Visual representation of risk factors
- List of concerning clauses with:
  - Section name
  - Concern description
  - Risk level badge
  - Recommendation
- Sortable by risk level

### Success Criteria
- [ ] Shows all risk factors
- [ ] Color-coded by severity
- [ ] Expandable details

---

## Task 4.8: Chat Interface Component

**File**: `frontend/src/components/ChatInterface.tsx`

### Requirements
- Message input with send button
- Message history display
- User/AI message styling
- Loading state during API call
- Cost display per query

### Success Criteria
- [ ] Can send questions
- [ ] Shows responses
- [ ] Displays cost per query
- [ ] Scroll to latest message

---

## Task 4.9: Cost Dashboard Component

**File**: `frontend/src/components/CostDashboard.tsx`

### Requirements
- Daily cost summary
- Breakdown by model (pie chart)
- Token usage stats
- Call counts
- Use recharts for visualization

### Success Criteria
- [ ] Displays total cost
- [ ] Pie chart shows model breakdown
- [ ] Token stats visible

---

## Integration Notes

- Use `NEXT_PUBLIC_API_URL` environment variable
- Handle CORS (backend allows all origins)
- Implement loading states for all API calls
- Use React Query or SWR for data fetching (optional)

---

## File Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx                    # Home/Upload
│   │   ├── dashboard/
│   │   │   └── [contractId]/
│   │   │       └── page.tsx            # Dashboard
│   │   └── layout.tsx                  # Root layout
│   ├── components/
│   │   ├── FileUpload.tsx
│   │   ├── ContractSummary.tsx
│   │   ├── RiskHeatmap.tsx
│   │   ├── ChatInterface.tsx
│   │   └── CostDashboard.tsx
│   └── lib/
│       └── api.ts
├── package.json
└── tailwind.config.ts
```

---

## Testing Checklist

```bash
# Start frontend
cd frontend
npm run dev

# Verify pages
# http://localhost:3000 - Upload page
# http://localhost:3000/dashboard/{id} - Dashboard

# Test with backend running
# 1. Upload a PDF
# 2. View analysis
# 3. Ask questions
# 4. Check cost dashboard
```

---

## UI/UX Guidelines

- Use consistent spacing (4, 8, 16, 24px)
- Risk colors: green (low), yellow (medium), red (high)
- Loading skeletons for async content
- Toast notifications for errors
- Responsive layout (mobile-friendly)
