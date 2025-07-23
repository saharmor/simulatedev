import { fetch } from "@tauri-apps/plugin-http";

const API_BASE_URL = "http://localhost:8000";

export interface Repository {
  owner: string;
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
  labels: Array<{
    name: string;
    color: string;
  }>;
  user: {
    login: string;
    avatar_url: string;
  };
  html_url: string;
  pull_request?: {
    url: string;
  };
}

export interface RepositoriesResponse {
  repositories: Repository[];
}

export interface IssuesResponse {
  issues: GitHubIssue[];
  total_count: number;
  page: number;
  per_page: number;
  has_next: boolean;
}

export class ApiService {
  async getRepositories(): Promise<Repository[]> {
    console.log("[ApiService] Fetching user repositories");
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/repositories`, {
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

      const data: RepositoriesResponse = await response.json();
      console.log(
        `[ApiService] Successfully fetched ${data.repositories.length} repositories`
      );

      return data.repositories;
    } catch (error) {
      console.error("[ApiService] Error fetching repositories:", error);
      throw error;
    }
  }

  async getRepositoryIssues(
    owner: string,
    repo: string,
    options: {
      state?: "open" | "closed" | "all";
      page?: number;
      per_page?: number;
      search?: string;
    } = {}
  ): Promise<IssuesResponse> {
    console.log(`[ApiService] Fetching issues for ${owner}/${repo}`);
    console.log(`[ApiService] Options:`, options);

    try {
      const params = new URLSearchParams();
      if (options.state) params.append("state", options.state);
      if (options.page) params.append("page", options.page.toString());
      if (options.per_page)
        params.append("per_page", options.per_page.toString());
      if (options.search) params.append("search", options.search);

      const url = `${API_BASE_URL}/api/github/repositories/${owner}/${repo}/issues?${params.toString()}`;
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
      console.log(
        `[ApiService] Successfully fetched ${data.issues.length} issues (total: ${data.total_count})`
      );

      return data;
    } catch (error) {
      console.error(
        `[ApiService] Error fetching issues for ${owner}/${repo}:`,
        error
      );
      throw error;
    }
  }

  // Helper method to filter issues vs pull requests
  filterIssuesOnly(issues: GitHubIssue[]): GitHubIssue[] {
    const filtered = issues.filter((issue) => !issue.pull_request);
    console.log(
      `[ApiService] Filtered ${filtered.length} issues from ${issues.length} total items`
    );
    return filtered;
  }

  // Helper method to filter pull requests only
  filterPullRequestsOnly(issues: GitHubIssue[]): GitHubIssue[] {
    const filtered = issues.filter((issue) => !!issue.pull_request);
    console.log(
      `[ApiService] Filtered ${filtered.length} pull requests from ${issues.length} total items`
    );
    return filtered;
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
