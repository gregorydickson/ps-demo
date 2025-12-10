# Legal Contract Intelligence Platform - Frontend

Next.js frontend for the AI-powered legal contract analysis platform.

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **Components**: shadcn/ui (Radix UI primitives)
- **Charts**: Recharts
- **HTTP Client**: Axios
- **Icons**: Lucide React

## Features

### 1. Contract Upload
- Drag-and-drop PDF upload
- File validation (PDF only, max 50MB)
- Upload progress indicator
- Automatic navigation to analysis dashboard

### 2. Contract Analysis Dashboard
- **Summary Tab**: Metadata, key terms, parties, risk score
- **Risk Analysis Tab**: Color-coded risk factors with recommendations
- **Chat Tab**: Interactive Q&A with the contract
- **Cost Analytics Tab**: Token usage and cost breakdown by model

### 3. UI Components
- Responsive design (mobile-friendly)
- Dark mode support
- Loading states and error handling
- Polished animations and transitions

## Getting Started

### Prerequisites
- Node.js 18+ and npm
- Backend API running on http://localhost:8000

### Installation

```bash
# Install dependencies
npm install

# Configure environment
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Start development server
npm run dev
```

Visit http://localhost:3000

### Build for Production

```bash
npm run build
npm start
```

## Project Structure

```
src/
├── app/
│   ├── page.tsx                    # Home/Upload page
│   ├── layout.tsx                  # Root layout
│   ├── globals.css                 # Global styles
│   └── dashboard/
│       └── [contractId]/
│           └── page.tsx            # Dynamic dashboard page
├── components/
│   ├── ui/                         # shadcn/ui components
│   ├── FileUpload.tsx             # Drag-and-drop upload
│   ├── ContractSummary.tsx        # Contract metadata display
│   ├── RiskHeatmap.tsx            # Risk visualization
│   ├── ChatInterface.tsx          # Q&A interface
│   └── CostDashboard.tsx          # Cost analytics
└── lib/
    ├── api.ts                      # API client functions
    └── utils.ts                    # Utility functions
```

## API Integration

The frontend connects to the FastAPI backend via:

- `POST /api/contracts/upload` - Upload PDF contract
- `GET /api/contracts/{id}` - Get contract details
- `POST /api/contracts/{id}/query` - Ask questions
- `GET /api/analytics/costs` - Get cost analytics

## Risk Color Coding

- **Green**: Low risk (score < 40)
- **Yellow**: Medium risk (score 40-69)
- **Red**: High risk (score ≥ 70)
