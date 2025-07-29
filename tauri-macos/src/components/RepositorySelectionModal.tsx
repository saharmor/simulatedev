import { useState, useEffect } from "react";
import { Search, GitBranch, Lock, Code, Calendar } from "lucide-react";
import { Repository } from "../services/apiService";

interface RepositorySelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRepositorySelect: (repository: Repository) => void;
  repositories: Repository[];
  isLoading: boolean;
  error: string | null;
}

export function RepositorySelectionModal({ 
  isOpen, 
  onClose, 
  onRepositorySelect, 
  repositories, 
  isLoading, 
  error 
}: RepositorySelectionModalProps) {
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (isOpen) {
      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          onClose();
        }
      };
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Filter repositories based on search query
  const filteredRepositories = repositories.filter(repo => {
    const searchLower = search.toLowerCase();
    const repoNameLower = repo.name.toLowerCase();
    const fullNameLower = repo.full_name.toLowerCase();
    const descriptionLower = (repo.description || '').toLowerCase();
    const languageLower = (repo.language || '').toLowerCase();
    
    return repoNameLower.includes(searchLower) || 
           fullNameLower.includes(searchLower) || 
           descriptionLower.includes(searchLower) ||
           languageLower.includes(searchLower);
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) return 'yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
    return `${Math.floor(diffDays / 365)} years ago`;
  };

  return (
    <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-start justify-center pt-32">
      <div className="bg-card border border-gray-300 rounded-lg shadow-2xl w-full max-w-2xl mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Select Repository</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search Input */}
        <div className="flex items-center gap-3 p-4 border-b border-gray-200">
          <Search className="w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search repositories by name, description, or language..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 bg-transparent outline-none text-sm"
            autoFocus
          />
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center">
              <div className="flex items-center justify-center gap-2 text-gray-500">
                <div className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin"></div>
                <span>Loading repositories...</span>
              </div>
            </div>
          ) : error ? (
            <div className="p-4 text-center">
              <div className="text-red-500">{error}</div>
            </div>
          ) : filteredRepositories.length === 0 ? (
            <div className="p-4 text-center">
              <div className="text-gray-500">
                {search ? `No repositories found matching "${search}"` : 'No repositories found'}
              </div>
            </div>
          ) : (
            <div className="p-2">
              {filteredRepositories.map((repo) => (
                <button
                  key={repo.full_name}
                  onClick={() => {
                    onRepositorySelect(repo);
                    onClose();
                  }}
                  className="w-full flex items-start gap-3 px-3 py-3 rounded text-sm hover:bg-gray-100 text-left transition-colors"
                >
                  <GitBranch className="w-4 h-4 text-gray-600 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono text-sm font-medium text-gray-900">
                        {repo.full_name}
                      </span>
                      {repo.private && (
                        <Lock className="w-3 h-3 text-gray-400" />
                      )}
                    </div>
                    {repo.description && (
                      <div className="text-sm text-gray-600 mb-2 line-clamp-2">
                        {repo.description}
                      </div>
                    )}
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      {repo.language && (
                        <div className="flex items-center gap-1">
                          <Code className="w-3 h-3" />
                          <span>{repo.language}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        <span>Updated {formatDate(repo.updated_at)}</span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 