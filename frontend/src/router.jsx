import { useEffect, useState } from 'react';

export function navigate(path) {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

export function useNavigate() {
  return navigate;
}

export function usePathname() {
  const [pathname, setPathname] = useState(window.location.pathname);
  useEffect(() => {
    const update = () => setPathname(window.location.pathname);
    window.addEventListener('popstate', update);
    return () => window.removeEventListener('popstate', update);
  }, []);
  return pathname;
}

export function useParams() {
  const pathname = usePathname();
  const match = pathname.match(/^\/runs\/([^/]+)$/);
  return { runId: match ? decodeURIComponent(match[1]) : undefined };
}

export function Link({ to, onClick, children, ...props }) {
  const follow = (event) => {
    onClick?.(event);
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate(to);
  };
  return <a href={to} onClick={follow} {...props}>{children}</a>;
}
