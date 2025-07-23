import { useState } from "react";
import { ChevronDown, Circle, Rocket, GitPullRequest, ExternalLink, FileText, Plus, Minus } from "lucide-react";
import { Button } from "./ui/button";

interface Issue {
  id: string;
  title: string;
  number: number;
  labels: string[];
  timeAgo: string;
}

interface PullRequest {
  id: string;
  title: string;
  number: number;
  repo: string;
  branch: string;
  filesChanged: number;
  additions: number;
  deletions: number;
  timeAgo: string;
}

type TabType = 'issues' | 'prs';

interface HomeScreenProps {
  onTaskStart: (issueId: string) => void;
  onCommandK: () => void;
}

const mockRepos = [
  'simulatedev',
  'whisper-playground', 
  'expense-tracker',
  'code-review-analysis'
];

const mockIssues: Issue[] = [
  {
    id: '61',
    title: 'Test changes to multiple files',
    number: 61,
    labels: [],
    timeAgo: 'Updated Jul 6, 2025 at 11:07 AM EDT'
  },
  {
    id: '60',
    title: 'Feature/updates and fixes',
    number: 60,
    labels: [],
    timeAgo: 'Updated Jul 6, 2025 at 11:07 AM EDT'
  }
];

const mockPRs: PullRequest[] = [
  {
    id: '45',
    title: 'Add new authentication flow',
    number: 45,
    repo: 'cbh123/narrator',
    branch: 'feature/auth-flow',
    filesChanged: 5,
    additions: 234,
    deletions: 12,
    timeAgo: 'Updated Jul 5, 2025 at 2:30 PM EDT'
  },
  {
    id: '42',
    title: 'Implement dark mode support',
    number: 42,
    repo: 'cbh123/narrator',
    branch: 'feature/dark-mode',
    filesChanged: 8,
    additions: 156,
    deletions: 23,
    timeAgo: 'Updated Jul 4, 2025 at 9:15 AM EDT'
  },
  {
    id: '38',
    title: 'Fix responsive design issues',
    number: 38,
    repo: 'cbh123/narrator',
    branch: 'fix/responsive-layout',
    filesChanged: 3,
    additions: 67,
    deletions: 45,
    timeAgo: 'Updated Jul 3, 2025 at 4:45 PM EDT'
  },
  {
    id: '35',
    title: 'Optimize database queries',
    number: 35,
    repo: 'cbh123/narrator',
    branch: 'perf/db-optimization',
    filesChanged: 4,
    additions: 89,
    deletions: 134,
    timeAgo: 'Updated Jul 2, 2025 at 11:20 AM EDT'
  }
];

export function HomeScreen({ onTaskStart, onCommandK }: HomeScreenProps) {
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [isRepoDropdownOpen, setIsRepoDropdownOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('issues');

  // Add global keyboard shortcut for Command+K
  useState(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onCommandK();
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  });

  return (
    <div className="flex-1 bg-background">
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
            >
              <span className="text-gray-700">
                {selectedRepo || 'Select a repository to work on'}
              </span>
              <ChevronDown className="w-4 h-4 text-gray-500" />
            </Button>

            {isRepoDropdownOpen && (
              <div className="absolute top-full left-0 right-0 max-w-md mx-auto mt-2 bg-card border border-gray-300 rounded-lg shadow-lg z-10">
                {mockRepos.map((repo) => (
                  <button
                    key={repo}
                    onClick={() => {
                      setSelectedRepo(repo);
                      setIsRepoDropdownOpen(false);
                    }}
                    className="w-full px-4 py-3 text-left hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg"
                  >
                    <span className="font-mono text-sm">{repo}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Issues and PRs List */}
        {selectedRepo && (
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-2 mb-6 justify-center">
              <button
                onClick={() => setActiveTab('issues')}
                className={`rounded-lg px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'issues'
                    ? 'bg-gray-200 text-gray-900'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-150'
                }`}
              >
                Issues ({mockIssues.length})
              </button>
              <button
                onClick={() => setActiveTab('prs')}
                className={`rounded-lg px-6 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'prs'
                    ? 'bg-gray-200 text-gray-900'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-150'
                }`}
              >
                Review PRs ({mockPRs.length})
              </button>
            </div>

            <div className="space-y-3">
              {activeTab === 'issues' && mockIssues.map((issue) => (
                <button
                  key={issue.id}
                  onClick={() => onTaskStart(issue.id)}
                  className="w-full p-4 bg-card border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <Circle className="w-4 h-4 text-success mt-1 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm text-gray-600">
                            cbh123/narrator
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
                      onClick={(e) => {
                        e.stopPropagation();
                        // Handle external link click
                      }}
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  </div>
                </button>
              ))}
              
              {activeTab === 'prs' && mockPRs.map((pr) => (
                <button
                  key={pr.id}
                  onClick={() => onTaskStart(pr.id)}
                  className="w-full bg-card border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <GitPullRequest className="w-4 h-4 text-gray-500 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-medium text-gray-900 mb-1">
                          {pr.title}
                        </h3>
                        <div className="flex items-center gap-4 text-xs text-gray-600 mb-1">
                          <span className="font-mono">{pr.branch}</span>
                          <span className="flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            {pr.filesChanged} files
                          </span>
                          <span className="flex items-center gap-1 text-success">
                            <Plus className="w-3 h-3" />
                            {pr.additions}
                          </span>
                          <span className="flex items-center gap-1 text-error">
                            <Minus className="w-3 h-3" />
                            {pr.deletions}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500">
                          {pr.timeAgo}
                        </p>
                      </div>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="text-gray-500 hover:text-gray-700 ml-2"
                      onClick={(e) => {
                        e.stopPropagation();
                        // Handle external link click
                      }}
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Command+K hint */}
        <div className="text-center mt-12">
          <p className="text-sm text-gray-500">
            Press <kbd className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">⌘K</kbd> to search tasks
          </p>
        </div>
      </div>
    </div>
  );
}