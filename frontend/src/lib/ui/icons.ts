// Single import point for Lucide icons (build-time, inline SVG — no runtime fetch).
import { House as _House } from 'lucide-svelte';

// lucide-svelte ships legacy class-component typings; alias one so
// consumers can type icon props without fighting Svelte 5's Component type.
export type IconComponent = typeof _House;

export {
  Flame,
  House,
  Plug,
  ReceiptText,
  Gauge,
  Scale,
  Settings,
  Plus,
  Upload,
  FileText,
  Zap,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Trash2,
  ExternalLink,
  Phone,
  Check,
  X,
  Inbox,
  LogOut,
  Pencil,
  CircleAlert,
  Trophy
} from 'lucide-svelte';
