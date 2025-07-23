# Deep Link Routing Guide

This document explains how to add new URL routes with deep links in the SimulateDev macOS app.

## Current Setup

The app is configured to handle deep links with the `simulatedev://` protocol. Deep link handling is implemented primarily in React with minimal Rust code.

### Existing Routes

- `simulatedev://login` - Opens the app on the login screen
- `simulatedev://home` - Opens the app on the home screen  
- `simulatedev://task?id=<taskId>` - Opens the app on a specific task screen

## Adding New Routes

### 1. Update the Deep Link Handler

Edit `/src/pages/Index.tsx` and add your new route to the switch statement in the `useEffect` hook:

```typescript
// Handle deep link navigation
useEffect(() => {
  if (deepLinkUrl) {
    const parsed = parseDeepLink(deepLinkUrl);
    if (parsed) {
      switch (parsed.path) {
        case '/login':
          setCurrentScreen('login');
          break;
        case '/home':
          setCurrentScreen('home');
          break;
        case '/task':
          const taskId = parsed.params.id;
          if (taskId) {
            setSelectedTaskId(taskId);
            setCurrentScreen('task');
          } else {
            setCurrentScreen('home');
          }
          break;
        // ADD YOUR NEW ROUTE HERE
        case '/your-new-route':
          // Handle your route logic
          // Access URL parameters via parsed.params
          break;
        default:
          setCurrentScreen(currentScreen === 'login' ? 'login' : 'home');
          break;
      }
    }
    clearDeepLink();
  }
}, [deepLinkUrl, parseDeepLink, clearDeepLink, currentScreen]);
```

### 2. Add Screen State (if needed)

If you're adding a completely new screen, update the `Screen` type:

```typescript
type Screen = 'login' | 'home' | 'task' | 'your-new-screen';
```

### 3. Add Routing Logic

Add the corresponding JSX rendering logic for your new screen:

```typescript
{currentScreen === 'your-new-screen' && (
  <YourNewScreen />
)}
```

## Parsing URL Parameters

The `parseDeepLink` function automatically parses URL parameters. For example:

- `simulatedev://settings?tab=profile&theme=dark`
- Parameters are accessible via `parsed.params.tab` and `parsed.params.theme`

### Example: Adding a Settings Route

1. **Add to switch statement:**
```typescript
case '/settings':
  const tab = parsed.params.tab || 'general';
  const theme = parsed.params.theme;
  setCurrentScreen('settings');
  setSettingsTab(tab);
  if (theme) setTheme(theme);
  break;
```

2. **Add screen type:**
```typescript
type Screen = 'login' | 'home' | 'task' | 'settings';
```

3. **Add rendering:**
```typescript
{currentScreen === 'settings' && (
  <SettingsScreen initialTab={settingsTab} />
)}
```

## Testing Deep Links

1. **Build the app:** `npm run tauri build`
2. **Install the built app**
3. **Test in browser address bar:** `simulatedev://your-route?param=value`
4. **Or use Terminal:** `open "simulatedev://your-route?param=value"`

## Architecture Notes

- **Rust code is minimal** - Only initializes the deep-link plugin
- **React handles routing** - All URL parsing and navigation logic is in React
- **No additional Rust changes needed** - The plugin registration in `src-tauri/src/lib.rs` handles all deep link events

## File Locations

- **React deep link hook:** `/src/hooks/useDeepLink.ts`
- **Main routing logic:** `/src/pages/Index.tsx`
- **Rust plugin setup:** `/src-tauri/src/lib.rs`
- **Tauri config:** `/src-tauri/tauri.conf.json`

## Common Patterns

### Route with Required Parameter
```typescript
case '/profile':
  const userId = parsed.params.userId;
  if (!userId) {
    // Handle missing required parameter
    setCurrentScreen('home');
    return;
  }
  setCurrentScreen('profile');
  setSelectedUserId(userId);
  break;
```

### Route with Optional Parameters
```typescript
case '/search':
  const query = parsed.params.q || '';
  const category = parsed.params.category || 'all';
  setCurrentScreen('search');
  setSearchQuery(query);
  setSearchCategory(category);
  break;
```

### Route with Complex State
```typescript
case '/workspace':
  const workspaceId = parsed.params.id;
  const view = parsed.params.view || 'overview';
  const highlightTask = parsed.params.highlight;
  
  setCurrentScreen('workspace');
  setSelectedWorkspaceId(workspaceId);
  setWorkspaceView(view);
  if (highlightTask) setHighlightedTaskId(highlightTask);
  break;
```