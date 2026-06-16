// Feature: Profile — local profile (avatar + display name), persisted per browser.
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ProfileStore {
  avatar: string | null; // data URL
  displayName: string;
  title: string;
  setAvatar: (a: string | null) => void;
  setDisplayName: (n: string) => void;
  setTitle: (t: string) => void;
}

export const useProfile = create<ProfileStore>()(
  persist(
    (set) => ({
      avatar: null,
      displayName: "",
      title: "",
      setAvatar: (avatar) => set({ avatar }),
      setDisplayName: (displayName) => set({ displayName }),
      setTitle: (title) => set({ title }),
    }),
    { name: "mawrid-profile" },
  ),
);
