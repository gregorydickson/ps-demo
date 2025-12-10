import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FileUpload from '@/components/FileUpload'
import * as api from '@/lib/api'

// Mock the API module
vi.mock('@/lib/api')

describe('FileUpload Component', () => {
  const mockOnUploadSuccess = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render upload zone with instructions', () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    expect(
      screen.getByText(/drop your pdf contract here/i)
    ).toBeInTheDocument()
    expect(screen.getByText(/or click to browse/i)).toBeInTheDocument()
  })

  it('should render select file button', () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const button = screen.getByText(/select file/i)
    expect(button).toBeInTheDocument()
  })

  it('should accept PDF files', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test content'], 'test.pdf', {
      type: 'application/pdf',
    })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })

    await userEvent.upload(input, file)

    // File name should be displayed
    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument()
    })
  })

  it('should reject non-PDF files with error message', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.txt', { type: 'text/plain' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })

    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText(/only pdf files are allowed/i)).toBeInTheDocument()
    })
  })

  it('should reject files larger than 50MB', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    // Create a mock large file
    const largeFile = new File(['x'.repeat(51 * 1024 * 1024)], 'large.pdf', {
      type: 'application/pdf',
    })

    // Override the size property
    Object.defineProperty(largeFile, 'size', {
      value: 51 * 1024 * 1024,
    })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })

    await userEvent.upload(input, largeFile)

    await waitFor(() => {
      expect(
        screen.getByText(/file size must be less than 50mb/i)
      ).toBeInTheDocument()
    })
  })

  it('should display file size in MB', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['x'.repeat(2 * 1024 * 1024)], 'test.pdf', {
      type: 'application/pdf',
    })

    // Override size
    Object.defineProperty(file, 'size', {
      value: 2 * 1024 * 1024,
    })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })

    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText(/2\.00 mb/i)).toBeInTheDocument()
    })
  })

  it('should show upload and clear buttons after file selection', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })

    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText(/upload & analyze/i)).toBeInTheDocument()
      expect(screen.getByText(/clear/i)).toBeInTheDocument()
    })
  })

  it('should clear selected file when clear button clicked', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })

    await userEvent.upload(input, file)

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument()
    })

    const clearButton = screen.getByText(/clear/i)
    await userEvent.click(clearButton)

    await waitFor(() => {
      expect(screen.queryByText('test.pdf')).not.toBeInTheDocument()
      expect(screen.getByText(/drop your pdf contract here/i)).toBeInTheDocument()
    })
  })

  it('should show progress bar during upload', async () => {
    const mockUpload = vi.fn((file, onProgress) => {
      // Simulate progress
      onProgress?.(50)
      return Promise.resolve({
        contract_id: 'test-123',
        message: 'Success',
      })
    })

    vi.mocked(api.uploadContract).mockImplementation(mockUpload)

    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })
    await userEvent.upload(input, file)

    const uploadButton = await screen.findByText(/upload & analyze/i)
    await userEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText(/uploading/i)).toBeInTheDocument()
    })
  })

  it('should call onUploadSuccess with contract ID after successful upload', async () => {
    const mockUpload = vi.fn().mockResolvedValue({
      contract_id: 'test-contract-123',
      message: 'Upload successful',
    })

    vi.mocked(api.uploadContract).mockImplementation(mockUpload)

    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })
    await userEvent.upload(input, file)

    const uploadButton = await screen.findByText(/upload & analyze/i)
    await userEvent.click(uploadButton)

    await waitFor(
      () => {
        expect(mockOnUploadSuccess).toHaveBeenCalledWith('test-contract-123')
      },
      { timeout: 2000 }
    )
  })

  it('should display error message on upload failure', async () => {
    const mockUpload = vi.fn().mockRejectedValue(new Error('Upload failed'))

    vi.mocked(api.uploadContract).mockImplementation(mockUpload)

    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })
    await userEvent.upload(input, file)

    const uploadButton = await screen.findByText(/upload & analyze/i)
    await userEvent.click(uploadButton)

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
    })
  })

  it('should disable file input during upload', async () => {
    const mockUpload = vi.fn(
      () =>
        new Promise((resolve) => {
          setTimeout(
            () => resolve({ contract_id: 'test-123', message: 'Success' }),
            100
          )
        })
    )

    vi.mocked(api.uploadContract).mockImplementation(mockUpload)

    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' }) as HTMLInputElement

    await userEvent.upload(input, file)

    const uploadButton = await screen.findByText(/upload & analyze/i)
    await userEvent.click(uploadButton)

    // Input should be disabled during upload
    await waitFor(() => {
      expect(input.disabled).toBe(true)
    })

    // Wait for upload to complete
    await waitFor(
      () => {
        expect(mockOnUploadSuccess).toHaveBeenCalled()
      },
      { timeout: 2000 }
    )
  })

  it('should handle drag and drop', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const dropZone = screen.getByText(/drop your pdf contract here/i).closest('div')

    expect(dropZone).toBeInTheDocument()

    // Simulate drag enter
    fireEvent.dragEnter(dropZone!, {
      dataTransfer: {
        files: [file],
      },
    })

    // Simulate drop
    fireEvent.drop(dropZone!, {
      dataTransfer: {
        files: [file],
      },
    })

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument()
    })
  })

  it('should update progress percentage during upload', async () => {
    let progressCallback: ((progress: number) => void) | undefined

    const mockUpload = vi.fn((file, onProgress) => {
      progressCallback = onProgress
      return new Promise((resolve) => {
        setTimeout(() => {
          progressCallback?.(75)
          resolve({ contract_id: 'test-123', message: 'Success' })
        }, 50)
      })
    })

    vi.mocked(api.uploadContract).mockImplementation(mockUpload)

    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    const input = screen.getByLabelText(/select file/i, { selector: 'input' })
    await userEvent.upload(input, file)

    const uploadButton = await screen.findByText(/upload & analyze/i)
    await userEvent.click(uploadButton)

    // Wait for progress to update
    await waitFor(
      () => {
        expect(screen.getByText(/75%/)).toBeInTheDocument()
      },
      { timeout: 2000 }
    )
  })

  it('should clear error when selecting new file', async () => {
    render(<FileUpload onUploadSuccess={mockOnUploadSuccess} />)

    // First upload a non-PDF to trigger error
    const badFile = new File(['test'], 'test.txt', { type: 'text/plain' })
    const input = screen.getByLabelText(/select file/i, { selector: 'input' })

    await userEvent.upload(input, badFile)

    await waitFor(() => {
      expect(screen.getByText(/only pdf files are allowed/i)).toBeInTheDocument()
    })

    // Now upload a valid PDF
    const goodFile = new File(['test'], 'test.pdf', { type: 'application/pdf' })

    await userEvent.upload(input, goodFile)

    // Error should be cleared
    await waitFor(() => {
      expect(
        screen.queryByText(/only pdf files are allowed/i)
      ).not.toBeInTheDocument()
    })
  })
})
