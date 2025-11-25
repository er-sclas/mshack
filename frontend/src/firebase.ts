/**
 * Firebase Configuration
 *
 * IMPORTANT: Replace the placeholder values below with your real Firebase config.
 *
 * To get your config:
 * 1. Go to https://console.firebase.google.com
 * 2. Select your project (or create one)
 * 3. Go to Project Settings (gear icon)
 * 4. Scroll down to "Your apps" section
 * 5. If no web app exists, click "Add app" and select Web (</>)
 * 6. Copy the firebaseConfig object values
 */

import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyDnB_ApyYxo29j29stTQ5xQrNuRUBLQF-Q",
  authDomain: "hackathon-2339c.firebaseapp.com",
  projectId: "hackathon-2339c",
  storageBucket: "hackathon-2339c.firebasestorage.app",
  messagingSenderId: "737615292578",
  appId: "1:737615292578:web:33198ec6a91b433d654ffb",
};

const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
