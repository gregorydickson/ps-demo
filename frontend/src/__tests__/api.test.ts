import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import {
  uploadContract,
  queryContract,
  getContractDetails,
  getCostAnalytics,
} from '@/lib/api'

// Mock axios
vi.mock('axios')
const mockedAxios = axios as any

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Setup default axios mock
    mockedAxios.create = vi.fn(() => ({
      post: vi.fn(),
      get: vi.fn(),
      interceptors: {
        response: {
          use: vi.fn(),
        },
      },
    }))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('uploadContract', () => {
    it('should upload file and return contract data', async () => {
      const mockResponse = {
        data: {
          contract_id: 'test-contract-123',
          message: 'Upload successful',
        },
      }

      // Create a mock axios instance
      const mockAxiosInstance = {
        post: vi.fn().mockResolvedValueOnce(mockResponse),
        get: vi.fn(),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      // Re-import to get fresh instance with mock
      const { uploadContract: upload } = await import('@/lib/api')

      const file = new File(['test content'], 'test.pdf', {
        type: 'application/pdf',
      })

      const result = await upload(file)

      expect(result.contract_id).toBe('test-contract-123')
      expect(mockAxiosInstance.post).toHaveBeenCalled()
    })

    it('should call onUploadProgress callback', async () => {
      const mockResponse = {
        data: { contract_id: 'test-123', message: 'Success' },
      }

      const mockAxiosInstance = {
        post: vi.fn((url, data, config) => {
          // Simulate progress
          if (config?.onUploadProgress) {
            config.onUploadProgress({ loaded: 50, total: 100 })
          }
          return Promise.resolve(mockResponse)
        }),
        get: vi.fn(),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { uploadContract: upload } = await import('@/lib/api')

      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })
      const progressCallback = vi.fn()

      await upload(file, progressCallback)

      expect(progressCallback).toHaveBeenCalledWith(50)
    })

    it('should handle upload errors gracefully', async () => {
      const mockAxiosInstance = {
        post: vi.fn().mockRejectedValueOnce(new Error('Network error')),
        get: vi.fn(),
        interceptors: {
          response: {
            use: vi.fn((success, error) => {
              // Call error handler
              return error
            }),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { uploadContract: upload } = await import('@/lib/api')

      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })

      await expect(upload(file)).rejects.toThrow()
    })

    it('should send file as FormData', async () => {
      const mockResponse = {
        data: { contract_id: 'test-123', message: 'Success' },
      }

      const mockAxiosInstance = {
        post: vi.fn().mockResolvedValueOnce(mockResponse),
        get: vi.fn(),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { uploadContract: upload } = await import('@/lib/api')

      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' })
      await upload(file)

      const callArgs = mockAxiosInstance.post.mock.calls[0]
      expect(callArgs[1]).toBeInstanceOf(FormData)
    })
  })

  describe('queryContract', () => {
    it('should send query and return answer', async () => {
      const mockResponse = {
        data: {
          answer: 'The payment terms are Net 30 days.',
          sources: ['Section 1.1'],
          cost: 0.001,
        },
      }

      const mockAxiosInstance = {
        post: vi.fn().mockResolvedValueOnce(mockResponse),
        get: vi.fn(),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { queryContract: query } = await import('@/lib/api')

      const result = await query('test-123', 'What are payment terms?')

      expect(result.answer).toBe('The payment terms are Net 30 days.')
      expect(result.sources).toEqual(['Section 1.1'])
      expect(result.cost).toBe(0.001)
    })

    it('should include contract ID in URL', async () => {
      const mockResponse = {
        data: { answer: 'Test answer', sources: [], cost: 0 },
      }

      const mockAxiosInstance = {
        post: vi.fn().mockResolvedValueOnce(mockResponse),
        get: vi.fn(),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { queryContract: query } = await import('@/lib/api')

      await query('contract-456', 'test query')

      const callArgs = mockAxiosInstance.post.mock.calls[0]
      expect(callArgs[0]).toContain('contract-456')
    })

    it('should send query in request body', async () => {
      const mockResponse = {
        data: { answer: 'Test', sources: [], cost: 0 },
      }

      const mockAxiosInstance = {
        post: vi.fn().mockResolvedValueOnce(mockResponse),
        get: vi.fn(),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { queryContract: query } = await import('@/lib/api')

      const testQuery = 'What is the termination clause?'
      await query('test-123', testQuery)

      const callArgs = mockAxiosInstance.post.mock.calls[0]
      expect(callArgs[1]).toEqual({ query: testQuery })
    })
  })

  describe('getContractDetails', () => {
    it('should fetch contract details by ID', async () => {
      const mockResponse = {
        data: {
          contract_id: 'test-123',
          metadata: {
            filename: 'contract.pdf',
            uploaded_at: '2025-01-01T00:00:00Z',
            parties: ['Party A', 'Party B'],
          },
          key_terms: [],
          risk_score: 5,
          risk_factors: [],
        },
      }

      const mockAxiosInstance = {
        post: vi.fn(),
        get: vi.fn().mockResolvedValueOnce(mockResponse),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { getContractDetails: getDetails } = await import('@/lib/api')

      const result = await getDetails('test-123')

      expect(result.contract_id).toBe('test-123')
      expect(result.metadata.filename).toBe('contract.pdf')
      expect(result.risk_score).toBe(5)
    })

    it('should use GET method', async () => {
      const mockResponse = {
        data: {
          contract_id: 'test-123',
          metadata: {},
          key_terms: [],
          risk_score: 0,
          risk_factors: [],
        },
      }

      const mockAxiosInstance = {
        post: vi.fn(),
        get: vi.fn().mockResolvedValueOnce(mockResponse),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { getContractDetails: getDetails } = await import('@/lib/api')

      await getDetails('test-123')

      expect(mockAxiosInstance.get).toHaveBeenCalled()
      expect(mockAxiosInstance.post).not.toHaveBeenCalled()
    })
  })

  describe('getCostAnalytics', () => {
    it('should fetch cost analytics', async () => {
      const mockResponse = {
        data: {
          date: '2025-01-01',
          total_cost: 0.05,
          model_breakdown: [],
          total_calls: 10,
          total_tokens: 5000,
        },
      }

      const mockAxiosInstance = {
        post: vi.fn(),
        get: vi.fn().mockResolvedValueOnce(mockResponse),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { getCostAnalytics: getAnalytics } = await import('@/lib/api')

      const result = await getAnalytics()

      expect(result.total_cost).toBe(0.05)
      expect(result.total_calls).toBe(10)
    })

    it('should support date parameter', async () => {
      const mockResponse = {
        data: {
          date: '2025-01-15',
          total_cost: 0.1,
          model_breakdown: [],
          total_calls: 20,
          total_tokens: 10000,
        },
      }

      const mockAxiosInstance = {
        post: vi.fn(),
        get: vi.fn().mockResolvedValueOnce(mockResponse),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { getCostAnalytics: getAnalytics } = await import('@/lib/api')

      await getAnalytics('2025-01-15')

      const callArgs = mockAxiosInstance.get.mock.calls[0]
      expect(callArgs[1]?.params).toEqual({ date: '2025-01-15' })
    })
  })

  describe('Error handling', () => {
    it('should handle server errors with detail field', async () => {
      const mockError = {
        response: {
          data: {
            detail: 'Contract not found',
          },
        },
      }

      const mockAxiosInstance = {
        post: vi.fn(),
        get: vi.fn().mockRejectedValueOnce(mockError),
        interceptors: {
          response: {
            use: vi.fn((success, errorHandler) => {
              // Simulate error interceptor
              return errorHandler(mockError)
            }),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { getContractDetails: getDetails } = await import('@/lib/api')

      await expect(getDetails('invalid-id')).rejects.toThrow()
    })

    it('should handle network errors', async () => {
      const mockError = {
        request: {},
        message: 'Network Error',
      }

      const mockAxiosInstance = {
        post: vi.fn(),
        get: vi.fn().mockRejectedValueOnce(mockError),
        interceptors: {
          response: {
            use: vi.fn(),
          },
        },
      }
      mockedAxios.create.mockReturnValueOnce(mockAxiosInstance)

      const { getContractDetails: getDetails } = await import('@/lib/api')

      await expect(getDetails('test-123')).rejects.toThrow()
    })
  })
})
