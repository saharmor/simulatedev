import { fetch } from "@tauri-apps/plugin-http";

const API_BASE_URL = "http://localhost:8000";

export interface Repository {
  name: string;
  full_name: string;
  url: string;
  description?: string;
  private: boolean;
  language?: string;
  updated_at: string;
}

export interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: "open" | "closed";
  created_at: string;
  updated_at: string;
  user_login: string;
  html_url: string;
}

export interface IssuesResponse {
  issues: GitHubIssue[];
  total_count: number;
  page: number;
  per_page: number;
  has_next: boolean;
}

export interface GitHubPullRequest {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: "open" | "closed";
  created_at: string;
  updated_at: string;
  user_login: string;
  html_url: string;
  head_ref: string;
  base_ref: string;
  draft: boolean;
}

export interface PullRequestsResponse {
  pull_requests: GitHubPullRequest[];
  total_count: number;
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface SinglePullRequest {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: string;
  created_at: string;
  updated_at: string;
  html_url: string;
  user_login: string;
  head_ref: string;
  base_ref: string;
  draft: boolean;
  additions: number;
  deletions: number;
  changed_files: number;
  mergeable?: boolean;
  mergeable_state?: string;
  merged: boolean;
  merged_at?: string;
  merged_by?: string;
  comments: number;
  review_comments: number;
  commits: number;
}

export interface TaskExecutionRequest {
  issue_url: string;
  agents: Array<{
    coding_ide: string;
    model: string;
    role: string;
  }>;
  create_pr: boolean;
  workflow_type: string;
  yolo_mode?: boolean;
  options?: Record<string, any>;
  task_prompt?: string;
  issue_number?: number;
  issue_title?: string;
}

export interface TaskExecutionResponse {
  task_id: string;
  status: string;
  repo_url: string;
  issue_number?: number;
  estimated_duration: number;
  created_at: string;
}

// TaskProgressUpdate moved to types/progress.ts as WebSocketProgressMessage

export class ApiService {
  async getRepositories(): Promise<Repository[]> {
    console.log("[ApiService] Fetching user repositories");
    try {
      const response = await fetch(`${API_BASE_URL}/api/github/repositories`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies for session authentication
      });

      console.log(
        `[ApiService] Repositories response status: ${response.status}`
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Repositories request failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to fetch repositories: ${response.status}`);
      }

      const data: Repository[] = await response.json();
      console.log(data);
      console.log(
        `[ApiService] Successfully fetched ${data.length} repositories`
      );

      return data;
    } catch (error) {
      console.error("[ApiService] Error fetching repositories:", error);
      throw error;
    }
  }

  async getRepositoryIssues(
    repo: string,
    options: {
      state?: "open" | "closed" | "all";
      page?: number;
      per_page?: number;
      search?: string;
    } = {}
  ): Promise<IssuesResponse> {
    console.log(`[ApiService] Fetching issues for ${repo}`);
    console.log(`[ApiService] Options:`, options);

    try {
      const params = new URLSearchParams();
      if (options.state) params.append("state", options.state);
      if (options.page) params.append("page", options.page.toString());
      if (options.per_page)
        params.append("per_page", options.per_page.toString());
      if (options.search) params.append("search", options.search);

      const url = `${API_BASE_URL}/api/github/repositories/${repo}/issues?${params.toString()}`;
      console.log(`[ApiService] Making request to: ${url}`);

      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies for session authentication
      });

      console.log(`[ApiService] Issues response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Issues request failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to fetch issues: ${response.status}`);
      }

      const data: IssuesResponse = await response.json();
      console.log(data);
      console.log(
        `[ApiService] Successfully fetched ${data.issues.length} issues (total: ${data.total_count})`
      );

      return data;
    } catch (error) {
      console.error(`[ApiService] Error fetching issues for ${repo}:`, error);
      throw error;
    }
  }

  async getRepositoryPullRequests(
    repo: string,
    options: {
      state?: "open" | "closed" | "all";
      page?: number;
      per_page?: number;
      search?: string;
    } = {}
  ): Promise<PullRequestsResponse> {
    console.log(`[ApiService] Fetching pull requests for ${repo}`);
    console.log(`[ApiService] Options:`, options);

    try {
      const params = new URLSearchParams();
      if (options.state) params.append("state", options.state);
      if (options.page) params.append("page", options.page.toString());
      if (options.per_page)
        params.append("per_page", options.per_page.toString());
      if (options.search) params.append("search", options.search);

      const url = `${API_BASE_URL}/api/github/repositories/${repo}/pulls?${params.toString()}`;
      console.log(`[ApiService] Making request to: ${url}`);

      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies for session authentication
      });

      console.log(`[ApiService] Pull requests response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Pull requests request failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to fetch pull requests: ${response.status}`);
      }

      const data: PullRequestsResponse = await response.json();
      console.log(data);
      console.log(
        `[ApiService] Successfully fetched ${data.pull_requests.length} pull requests (total: ${data.total_count})`
      );

      return data;
    } catch (error) {
      console.error(`[ApiService] Error fetching pull requests for ${repo}:`, error);
      throw error;
    }
  }

  async executeTask(taskData: TaskExecutionRequest): Promise<TaskExecutionResponse> {
    console.log("[ApiService] Executing task with data:", taskData);
    console.log("[ApiService] Task data JSON:", JSON.stringify(taskData, null, 2));
    try {
      const response = await fetch(`${API_BASE_URL}/api/tasks/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(taskData),
      });

      console.log(`[ApiService] Task execution response status: ${response.status}`);
      console.log(`[ApiService] Task execution response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Task execution failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to execute task: ${response.status}`);
      }

      const data: TaskExecutionResponse = await response.json();
      console.log(`[ApiService] Task execution successful: ${data.task_id}`);
      console.log(`[ApiService] Full task execution response:`, data);
      console.log(`[ApiService] Task execution response JSON:`, JSON.stringify(data, null, 2));
      return data;
    } catch (error) {
      console.error("[ApiService] Error executing task:", error);
      throw error;
    }
  }

  async executeSequentialTask(taskData: TaskExecutionRequest): Promise<TaskExecutionResponse> {
    console.log("[ApiService] Executing sequential task with data:", taskData);
    console.log("[ApiService] Sequential task data JSON:", JSON.stringify(taskData, null, 2));
    try {
      const response = await fetch(`${API_BASE_URL}/api/tasks/execute-sequential`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(taskData),
      });

      console.log(`[ApiService] Sequential task execution response status: ${response.status}`);
      console.log(`[ApiService] Sequential task execution response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Sequential task execution failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to execute sequential task: ${response.status}`);
      }

      const data: TaskExecutionResponse = await response.json();
      console.log(`[ApiService] Sequential task execution successful: ${data.task_id}`);
      console.log(`[ApiService] Full sequential task execution response:`, data);
      console.log(`[ApiService] Sequential task execution response JSON:`, JSON.stringify(data, null, 2));
      return data;
    } catch (error) {
      console.error("[ApiService] Error executing sequential task:", error);
      throw error;
    }
  }

  async getTaskStatus(taskId: string): Promise<any> {
    console.log(`[ApiService] Fetching task status for: ${taskId}`);
    try {
      const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      });

      console.log(`[ApiService] Task status response status: ${response.status}`);
      console.log(`[ApiService] Task status response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Task status request failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to fetch task status: ${response.status}`);
      }

      const data = await response.json();
      console.log(`[ApiService] Task status fetched successfully`);
      console.log(`[ApiService] Full task status response:`, data);
      console.log(`[ApiService] Task status response JSON:`, JSON.stringify(data, null, 2));
      return data;
    } catch (error) {
      console.error(`[ApiService] Error fetching task status:`, error);
      throw error;
    }
  }

  async getPullRequest(owner: string, repo: string, prNumber: number): Promise<SinglePullRequest> {
    console.log(`[ApiService] Fetching pull request ${prNumber} for ${owner}/${repo}`);
    try {
      const response = await fetch(`${API_BASE_URL}/api/github/repositories/${owner}/${repo}/pulls/${prNumber}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      });

      console.log(`[ApiService] Pull request response status: ${response.status}`);
      console.log(`[ApiService] Pull request response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Pull request request failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to fetch pull request: ${response.status}`);
      }

      const data: SinglePullRequest = await response.json();
      console.log(`[ApiService] Successfully fetched pull request ${prNumber}`);
      console.log(`[ApiService] Full pull request response:`, data);
      console.log(`[ApiService] Pull request response JSON:`, JSON.stringify(data, null, 2));
      return data;
    } catch (error) {
      console.error(`[ApiService] Error fetching pull request:`, error);
      throw error;
    }
  }

  async getTaskStepsPlan(taskId: string): Promise<any> {
    console.log(`[ApiService] Fetching steps plan for task: ${taskId}`);
    try {
      const response = await fetch(`${API_BASE_URL}/api/tasks/${taskId}/steps`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
      });

      console.log(`[ApiService] Steps plan response status: ${response.status}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error(
          `[ApiService] Steps plan request failed: ${response.status} - ${errorText}`
        );
        throw new Error(`Failed to fetch steps plan: ${response.status}`);
      }

      const data = await response.json();
      console.log(`[ApiService] Successfully fetched steps plan`);
      console.log(`[ApiService] Steps plan response:`, data);
      return data;
    } catch (error) {
      console.error(`[ApiService] Error fetching steps plan:`, error);
      throw error;
    }
  }

  // Helper method to format time ago (simple implementation)
  formatTimeAgo(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      if (diffHours === 0) {
        const diffMins = Math.floor(diffMs / (1000 * 60));
        return `Updated ${diffMins} minutes ago`;
      }
      return `Updated ${diffHours} hours ago`;
    } else if (diffDays === 1) {
      return "Updated yesterday";
    } else {
      return `Updated ${diffDays} days ago`;
    }
  }
}

export const apiService = new ApiService();
