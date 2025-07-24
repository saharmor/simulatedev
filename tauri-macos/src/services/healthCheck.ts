import { fetch } from "@tauri-apps/plugin-http";

const API_BASE_URL = 'http://localhost:8000';
const HEALTH_CHECK_INTERVAL = 30000; // 30 seconds

export interface HealthCheckResult {
  isHealthy: boolean;
  error?: string;
  consecutiveFailures?: number;
}

export class HealthCheckService {
  private intervalId: NodeJS.Timeout | null = null;
  private isRunning = false;
  private consecutiveFailures = 0;

  async checkHealth(): Promise<HealthCheckResult> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        this.consecutiveFailures = 0;
        return { isHealthy: true, consecutiveFailures: 0 };
      } else {
        this.consecutiveFailures++;
        return { 
          isHealthy: false, 
          error: `Server returned ${response.status}`,
          consecutiveFailures: this.consecutiveFailures
        };
      }
    } catch (error) {
      this.consecutiveFailures++;
      return { 
        isHealthy: false, 
        error: error instanceof Error ? error.message : 'Unknown error',
        consecutiveFailures: this.consecutiveFailures
      };
    }
  }

  startPeriodicHealthChecks(onHealthChange: (result: HealthCheckResult) => void): void {
    if (this.isRunning) {
      return;
    }

    this.isRunning = true;
    
    // Check immediately
    this.checkHealth().then(onHealthChange);
    
    // Set up periodic checks
    this.intervalId = setInterval(async () => {
      const result = await this.checkHealth();
      onHealthChange(result);
    }, HEALTH_CHECK_INTERVAL);
  }

  stopPeriodicHealthChecks(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.isRunning = false;
  }

  resetFailureCount(): void {
    this.consecutiveFailures = 0;
  }

  getConsecutiveFailures(): number {
    return this.consecutiveFailures;
  }
}

export const healthCheckService = new HealthCheckService();