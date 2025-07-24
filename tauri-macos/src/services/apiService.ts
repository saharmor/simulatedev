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
