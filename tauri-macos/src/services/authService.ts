import { fetch } from "@tauri-apps/plugin-http";
import { openUrl } from "@tauri-apps/plugin-opener";

const API_BASE_URL = "http://localhost:8000";

export class AuthService {
  async initiateGitHubOAuth(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/github`);

      if (!response.ok) {
        throw new Error(`GitHub OAuth request failed: ${response.status}`);
      }

      // The backend returns a redirect response, we need to get the redirect URL
      const redirectUrl = response.url;

      // Open the GitHub OAuth URL in the default browser
      await openUrl(redirectUrl);
    } catch (error) {
      console.error("GitHub OAuth initiation failed:", error);
      throw error;
    }
  }
}

export const authService = new AuthService();
