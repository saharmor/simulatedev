import { fetch } from "@tauri-apps/plugin-http";
import { openUrl } from "@tauri-apps/plugin-opener";

const API_BASE_URL = "http://localhost:8000";

export interface User {
  id: number;
  github_username: string;
  github_email?: string;
  avatar_url?: string;
}

export interface SessionResponse {
  user: User;
  session_expires_at: string;
}

export class AuthService {
  private readonly SESSION_TOKEN_KEY = 'session_token';
  private readonly USER_DATA_KEY = 'user_data';

  async initiateGitHubOAuth(): Promise<void> {
    console.log('[AuthService] Initiating GitHub OAuth flow');
    try {
      console.log(`[AuthService] Making request to: ${API_BASE_URL}/api/auth/github`);
      const response = await fetch(`${API_BASE_URL}/api/auth/github`);

      console.log(`[AuthService] GitHub OAuth response status: ${response.status}`);
      console.log(`[AuthService] GitHub OAuth response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const error = `GitHub OAuth request failed: ${response.status}`;
        console.error(`[AuthService] ${error}`);
        throw new Error(error);
      }

      // The backend returns a redirect response, we need to get the redirect URL
      const redirectUrl = response.url;
      console.log(`[AuthService] Got redirect URL: ${redirectUrl}`);

      // Open the GitHub OAuth URL in the default browser
      console.log('[AuthService] Opening GitHub OAuth URL in browser');
      await openUrl(redirectUrl);
      console.log('[AuthService] Successfully opened GitHub OAuth URL');
    } catch (error) {
      console.error("[AuthService] GitHub OAuth initiation failed:", error);
      throw error;
    }
  }

  async createSession(sessionCode: string): Promise<SessionResponse> {
    console.log(`[AuthService] Creating session with code: ${sessionCode.substring(0, 8)}...`);
    try {
      const requestBody = { session_code: sessionCode };
      console.log(`[AuthService] Making POST request to: ${API_BASE_URL}/api/auth/session`);
      console.log(`[AuthService] Request body:`, requestBody);
      
      const response = await fetch(`${API_BASE_URL}/api/auth/session`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
        credentials: 'include', // Include cookies and allow setting cookies
      });

      console.log(`[AuthService] Session creation response status: ${response.status}`);
      console.log(`[AuthService] Session creation response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        const errorText = await response.text();
        console.error(`[AuthService] Session creation failed with status ${response.status}: ${errorText}`);
        throw new Error(`Session creation failed: ${response.status}`);
      }

      const sessionData: SessionResponse = await response.json();
      console.log(`[AuthService] Successfully created session for user: ${sessionData.user.github_username}`);
      console.log(`[AuthService] Session expires at: ${sessionData.session_expires_at}`);
      
      // Store session token and user data in localStorage
      console.log(`[AuthService] Storing session token in localStorage (key: ${this.SESSION_TOKEN_KEY})`);
      localStorage.setItem(this.SESSION_TOKEN_KEY, sessionCode);
      
      console.log(`[AuthService] Storing user data in localStorage (key: ${this.USER_DATA_KEY})`);
      localStorage.setItem(this.USER_DATA_KEY, JSON.stringify(sessionData.user));
      
      console.log(`[AuthService] Successfully stored auth data for user: ${sessionData.user.github_username}`);
      return sessionData;
    } catch (error) {
      console.error("[AuthService] Session creation failed:", error);
      throw error;
    }
  }

  async getCurrentUser(): Promise<User | null> {
    console.log('[AuthService] Getting current user');
    try {
      const sessionToken = localStorage.getItem(this.SESSION_TOKEN_KEY);
      console.log(`[AuthService] Session token exists: ${!!sessionToken}`);
      
      if (!sessionToken) {
        console.log('[AuthService] No session token found, user not authenticated');
        return null;
      }

      console.log(`[AuthService] Found session token: ${sessionToken.substring(0, 8)}...`);
      console.log(`[AuthService] Making GET request to: ${API_BASE_URL}/api/auth/me`);
      
      const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        method: 'GET',
        credentials: 'include', // Include cookies for session authentication
      });

      console.log(`[AuthService] Current user response status: ${response.status}`);
      console.log(`[AuthService] Current user response headers:`, Object.fromEntries(response.headers.entries()));

      if (!response.ok) {
        console.warn(`[AuthService] Session validation failed with status ${response.status}, clearing auth data`);
        // Session is invalid, clear local storage
        this.clearAuthData();
        return null;
      }

      const user: User = await response.json();
      console.log(`[AuthService] Successfully validated session for user: ${user.github_username}`);
      console.log(`[AuthService] User data:`, {
        id: user.id,
        github_username: user.github_username,
        github_email: user.github_email,
        has_avatar: !!user.avatar_url
      });
      
      // Update stored user data
      console.log('[AuthService] Updating stored user data in localStorage');
      localStorage.setItem(this.USER_DATA_KEY, JSON.stringify(user));
      
      return user;
    } catch (error) {
      console.error("[AuthService] Get current user failed:", error);
      // Clear auth data on error
      console.log('[AuthService] Clearing auth data due to error');
      this.clearAuthData();
      return null;
    }
  }

  getStoredUser(): User | null {
    console.log('[AuthService] Getting stored user data');
    try {
      const userData = localStorage.getItem(this.USER_DATA_KEY);
      console.log(`[AuthService] Stored user data exists: ${!!userData}`);
      
      if (!userData) {
        console.log('[AuthService] No stored user data found');
        return null;
      }
      
      const user = JSON.parse(userData);
      console.log(`[AuthService] Retrieved stored user: ${user.github_username}`);
      return user;
    } catch (error) {
      console.error("[AuthService] Failed to parse stored user data:", error);
      return null;
    }
  }

  isAuthenticated(): boolean {
    const hasToken = !!localStorage.getItem(this.SESSION_TOKEN_KEY);
    console.log(`[AuthService] Is authenticated: ${hasToken}`);
    return hasToken;
  }

  clearAuthData(): void {
    console.log('[AuthService] Clearing authentication data');
    console.log(`[AuthService] Removing ${this.SESSION_TOKEN_KEY} from localStorage`);
    localStorage.removeItem(this.SESSION_TOKEN_KEY);
    
    console.log(`[AuthService] Removing ${this.USER_DATA_KEY} from localStorage`);
    localStorage.removeItem(this.USER_DATA_KEY);
    
    console.log('[AuthService] Authentication data cleared successfully');
  }
}

export const authService = new AuthService();
