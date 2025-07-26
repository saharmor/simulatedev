import { useState, useEffect } from "react";
import {
  ChevronDown,
  Circle,
  Rocket,
  GitPullRequest,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { Button } from "./ui/button";
import { apiService, Repository } from "../services/apiService";
import { openUrl } from "@tauri-apps/plugin-opener";
import { AgentSelectionModal } from "./AgentSelectionModal";

// Convert GitHub API types to frontend types for consistency
interface Issue {
  id: string;
  title: string;
  number: number;
  timeAgo: string;
  htmlUrl: string;
  user: string;
}

interface PullRequest {
  id: string;
  title: string;
  number: number;
  repo: string;
  timeAgo: string;
  htmlUrl: string;
  user: string;
}

type TabType = "issues" | "prs";

interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
}

interface HomeScreenProps {
  onTaskStart: (issue: Issue, agent: Agent, repository?: Repository) => void;
  onCommandK: () => void;
}

export function HomeScreen({ onTaskStart, onCommandK }: HomeScreenProps) {
  // Repository state
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [isRepoDropdownOpen, setIsRepoDropdownOpen] = useState(false);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);
  const [repoError, setRepoError] = useState<string | null>(null);

  // Issues/PRs state
  const [issues, setIssues] = useState<Issue[]>([]);
  const [pullRequests, setPullRequests] = useState<PullRequest[]>([]);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("issues");

  // Agent selection modal state
  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);

  // Fetch repositories on component mount
  useEffect(() => {
    const fetchRepositories = async () => {
      console.log("[HomeScreen] Fetching repositories on mount");
      try {
        setIsLoadingRepos(true);
        setRepoError(null);
        const repos = await apiService.getRepositories();
        console.log(
          `[HomeScreen] Successfully loaded ${repos.length} repositories`
        );
        setRepositories(repos);
      } catch (error) {
        console.error("[HomeScreen] Failed to fetch repositories:", error);
        setRepoError("Failed to load repositories");
      } finally {
        setIsLoadingRepos(false);
      }
    };

    fetchRepositories();
  }, []);

  // Fetch issues and PRs when a repository is selected
  useEffect(() => {
    const fetchRepositoryData = async () => {
      if (!selectedRepo) {
        console.log("[HomeScreen] No repository selected, clearing data");
        setIssues([]);
        setPullRequests([]);
        return;
      }

      console.log(
        `[HomeScreen] Fetching data for repository: ${selectedRepo.full_name}`
      );
      try {
        setIsLoadingData(true);
        setDataError(null);
        console.log(selectedRepo);

        const [issuesResponse, prsResponse] = await Promise.all([
          apiService.getRepositoryIssues(selectedRepo.full_name, {
            state: "open",
            per_page: 50,
          }),
          apiService.getRepositoryPullRequests(selectedRepo.full_name, {
            state: "open",
            per_page: 50,
          }),
        ]);

        // Convert GitHub API data to frontend format
        const convertedIssues: Issue[] = issuesResponse.issues.map((issue) => ({
          id: issue.id.toString(),
          title: issue.title,
          number: issue.number,
          timeAgo: apiService.formatTimeAgo(issue.updated_at),
          htmlUrl: issue.html_url,
          user: issue.user_login,
        }));

        const convertedPRs: PullRequest[] = prsResponse.pull_requests.map(
          (pr) => ({
            id: pr.id.toString(),
            title: pr.title,
            number: pr.number,
            repo: selectedRepo.full_name,
            timeAgo: apiService.formatTimeAgo(pr.updated_at),
            htmlUrl: pr.html_url,
            user: pr.user_login,
          })
        );

        console.log(
          `[HomeScreen] Successfully loaded ${convertedIssues.length} issues and ${convertedPRs.length} PRs`
        );
        setIssues(convertedIssues);
        setPullRequests(convertedPRs);
      } catch (error) {
        console.error(
          `[HomeScreen] Failed to fetch data for ${selectedRepo.full_name}:`,
          error
        );
        setDataError("Failed to load repository data");
      } finally {
        setIsLoadingData(false);
      }
    };

    fetchRepositoryData();
  }, [selectedRepo]);

  // Add global keyboard shortcut for Command+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onCommandK();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCommandK]);

  // Modal handlers
  const handleIssueClick = (issue: Issue) => {
    setSelectedIssue(issue);
    setIsAgentModalOpen(true);
  };

  const handleAgentSelect = (agent: Agent) => {
    if (selectedIssue) {
      console.log(
        `[HomeScreen] Starting task for issue: ${selectedIssue.number} with agent: ${agent.name}`
      );
      onTaskStart(selectedIssue, agent, selectedRepo || undefined);
    }
    setIsAgentModalOpen(false);
    setSelectedIssue(null);
  };

  const handleModalClose = () => {
    setIsAgentModalOpen(false);
    setSelectedIssue(null);
  };

  return (
    <div className="flex-1 bg-background overflow-y-auto">
      <div className="max-w-4xl mx-auto py-32 px-8">
        {/* Logo */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-mono font-semibold text-foreground tracking-tight flex items-center justify-center gap-3">
            <Rocket className="w-12 h-12" />
            SimulateDev
          </h1>
        </div>

        {/* Repository Selection */}
        <div className="mb-8">
          <div className="relative">
            <Button
              onClick={() => setIsRepoDropdownOpen(!isRepoDropdownOpen)}
              variant="outline"
              className="w-full max-w-md mx-auto flex items-center justify-between p-4 h-auto border-gray-300 hover:bg-gray-50"
              disabled={isLoadingRepos}
            >
              <span className="text-gray-700">
                {isLoadingRepos ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading repositories...
                  </span>
                ) : repoError ? (
                  <span className="text-red-500">{repoError}</span>
                ) : selectedRepo ? (
                  selectedRepo.full_name
                ) : (
                  "Select a repository to work on"
                )}
              </span>
              <ChevronDown className="w-4 h-4 text-gray-500" />
            </Button>

            {isRepoDropdownOpen && !isLoadingRepos && !repoError && (
              <div className="absolute top-full left-0 right-0 max-w-md mx-auto mt-2 bg-card border border-gray-300 rounded-lg shadow-lg z-10 max-h-64 overflow-y-auto">
                {repositories.length === 0 ? (
                  <div className="px-4 py-3 text-gray-500 text-sm">
                    No repositories found
                  </div>
                ) : (
                  repositories.map((repo) => (
                    <button
                      key={repo.full_name}
                      onClick={() => {
                        console.log(
                          `[HomeScreen] Selected repository: ${repo.full_name}`
                        );
                        setSelectedRepo(repo);
                        setIsRepoDropdownOpen(false);
                      }}
                      className="w-full px-4 py-3 text-left hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg"
                    >
                      <div>
                        <span className="font-mono text-sm font-medium">
                          {repo.full_name}
                        </span>
                        {repo.description && (
                          <p className="text-xs text-gray-500 mt-1 truncate">
                            {repo.description}
                          </p>
                        )}
                        <div className="flex items-center gap-3 mt-1">
                          {repo.language && (
                            <span className="text-xs text-gray-400">
                              {repo.language}
                            </span>
                          )}
                          {repo.private && (
                            <span className="text-xs text-gray-400">
                              Private
                            </span>
                          )}
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Issues and PRs List */}
        {selectedRepo && (
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-2 mb-6 justify-center">
              <button
                onClick={() => setActiveTab("issues")}
                className={`rounded-lg px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === "issues"
                    ? "bg-gray-200 text-gray-900"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-150"
                }`}
              >
                Issues ({isLoadingData ? "..." : issues.length})
              </button>
              <button
                onClick={() => setActiveTab("prs")}
                className={`rounded-lg px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === "prs"
                    ? "bg-gray-200 text-gray-900"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-150"
                }`}
              >
                Review PRs ({isLoadingData ? "..." : pullRequests.length})
              </button>
            </div>

            {isLoadingData ? (
              <div className="flex items-center justify-center py-12">
                <div className="flex items-center gap-3 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Loading {selectedRepo.full_name} data...</span>
                </div>
              </div>
            ) : dataError ? (
              <div className="text-center py-12">
                <p className="text-red-500 mb-4">{dataError}</p>
                <Button
                  onClick={() => {
                    // Trigger a refetch by clearing and re-setting selectedRepo
                    const currentRepo = selectedRepo;
                    setSelectedRepo(null);
                    setTimeout(() => setSelectedRepo(currentRepo), 100);
                  }}
                  variant="outline"
                >
                  Try Again
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {activeTab === "issues" && (
                  <>
                    {issues.length === 0 ? (
                      <div className="text-center py-12 text-gray-500">
                        No open issues found in {selectedRepo.full_name}
                      </div>
                    ) : (
                      issues.map((issue) => (
                        <button
                          key={issue.id}
                          onClick={() => handleIssueClick(issue)}
                          className="w-full p-4 bg-card border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-start gap-3 flex-1">
                              <Circle className="w-4 h-4 text-success mt-1 flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="font-mono text-sm text-gray-600">
                                    {selectedRepo.full_name}
                                  </span>
                                  <span className="font-mono text-sm text-gray-400">
                                    #{issue.number}
                                  </span>
                                </div>
                                <h3 className="text-sm font-medium text-gray-900 mb-2">
                                  {issue.title}
                                </h3>
                                <p className="text-xs text-gray-500">
                                  {issue.timeAgo}
                                </p>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-gray-500 hover:text-gray-700 ml-2"
                              onClick={async (e) => {
                                e.stopPropagation();
                                console.log(
                                  `[HomeScreen] Opening external link: ${issue.htmlUrl}`
                                );
                                try {
                                  await openUrl(issue.htmlUrl);
                                } catch (error) {
                                  console.error(
                                    "Failed to open external link:",
                                    error
                                  );
                                }
                              }}
                            >
                              <ExternalLink className="w-4 h-4" />
                            </Button>
                          </div>
                        </button>
                      ))
                    )}
                  </>
                )}

                {activeTab === "prs" && (
                  <>
                    {pullRequests.length === 0 ? (
                      <div className="text-center py-12 text-gray-500">
                        No open pull requests found in {selectedRepo.full_name}
                      </div>
                    ) : (
                      pullRequests.map((pr) => (
                        <button
                          key={pr.id}
                          onClick={() => {
                            // Convert PR to Issue-like object for now
                            const prAsIssue: Issue = {
                              id: pr.id,
                              title: pr.title,
                              number: pr.number,
                              timeAgo: pr.timeAgo,
                              htmlUrl: pr.htmlUrl,
                              user: pr.user
                            };
                            handleIssueClick(prAsIssue);
                          }}
                          className="w-full bg-card border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors text-left"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex items-start gap-3 flex-1">
                              <GitPullRequest className="w-4 h-4 text-success flex-shrink-0" />
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="font-mono text-sm text-gray-600">
                                    {selectedRepo.full_name}
                                  </span>
                                  <span className="font-mono text-sm text-gray-400">
                                    #{pr.number}
                                  </span>
                                </div>
                                <h3 className="text-sm font-medium text-gray-900 mb-2">
                                  {pr.title}
                                </h3>
                                <p className="text-xs text-gray-500">
                                  {pr.timeAgo}
                                </p>
                              </div>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-gray-500 hover:text-gray-700 ml-2"
                              onClick={async (e) => {
                                e.stopPropagation();
                                console.log(
                                  `[HomeScreen] Opening external link: ${pr.htmlUrl}`
                                );
                                try {
                                  await openUrl(pr.htmlUrl);
                                } catch (error) {
                                  console.error(
                                    "Failed to open external link:",
                                    error
                                  );
                                }
                              }}
                            >
                              <ExternalLink className="w-4 h-4" />
                            </Button>
                          </div>
                        </button>
                      ))
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Command+K hint */}
        <div className="text-center mt-12">
          <p className="text-sm text-gray-500">
            Press{" "}
            <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
              ⌘K
            </kbd>{" "}
            to search tasks
          </p>
        </div>
      </div>

      {/* Agent Selection Modal */}
      <AgentSelectionModal
        isOpen={isAgentModalOpen}
        onClose={handleModalClose}
        onAgentSelect={handleAgentSelect}
      />
    </div>
  );
}
