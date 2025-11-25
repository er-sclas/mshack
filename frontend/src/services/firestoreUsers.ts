/**
 * Firestore Users Service
 *
 * Basic CRUD operations for a users collection in Firestore.
 * This is a utility module that can be used for any user-related data.
 *
 * To use this service, ensure your Firebase config in src/firebase.ts
 * is properly set up with your project credentials.
 */

import { db } from "../firebase";
import {
  collection,
  addDoc,
  getDocs,
  doc,
  getDoc,
  updateDoc,
  deleteDoc,
  serverTimestamp,
  query,
  orderBy,
  limit,
  DocumentData,
} from "firebase/firestore";

// Collection reference
const usersCollection = collection(db, "users");

// User data interface
export interface UserData {
  name?: string;
  email?: string;
  createdAt?: string;
  [key: string]: unknown;
}

export interface User extends UserData {
  id: string;
}

/**
 * Create a new user document
 *
 * @param data - User data to store
 * @returns The ID of the newly created document
 *
 * @example
 * const userId = await createUser({ name: "John Doe", email: "john@example.com" });
 */
export async function createUser(data: UserData): Promise<string> {
  try {
    const docRef = await addDoc(usersCollection, {
      ...data,
      createdAt: serverTimestamp(),
    });
    return docRef.id;
  } catch (error) {
    console.error("Error creating user:", error);
    throw error;
  }
}

/**
 * Get all users from the collection
 *
 * @param maxResults - Maximum number of users to return (default: 100)
 * @returns Array of user objects with their IDs
 *
 * @example
 * const users = await getAllUsers();
 * users.forEach(user => console.log(user.name));
 */
export async function getAllUsers(maxResults: number = 100): Promise<User[]> {
  try {
    const q = query(
      usersCollection,
      orderBy("createdAt", "desc"),
      limit(maxResults)
    );
    const snapshot = await getDocs(q);
    return snapshot.docs.map((doc) => ({
      id: doc.id,
      ...(doc.data() as DocumentData),
    })) as User[];
  } catch (error) {
    console.error("Error getting users:", error);
    throw error;
  }
}

/**
 * Get a single user by ID
 *
 * @param id - The document ID of the user
 * @returns The user object or null if not found
 *
 * @example
 * const user = await getUserById("abc123");
 * if (user) {
 *   console.log(user.name);
 * }
 */
export async function getUserById(id: string): Promise<User | null> {
  try {
    const docRef = doc(db, "users", id);
    const docSnap = await getDoc(docRef);

    if (docSnap.exists()) {
      return { id: docSnap.id, ...(docSnap.data() as DocumentData) } as User;
    }
    return null;
  } catch (error) {
    console.error("Error getting user:", error);
    throw error;
  }
}

/**
 * Update an existing user document (partial update)
 *
 * @param id - The document ID of the user
 * @param data - Fields to update
 *
 * @example
 * await updateUser("abc123", { name: "Jane Doe" });
 */
export async function updateUser(
  id: string,
  data: Partial<UserData>
): Promise<void> {
  try {
    const docRef = doc(db, "users", id);
    await updateDoc(docRef, {
      ...data,
      updatedAt: serverTimestamp(),
    });
  } catch (error) {
    console.error("Error updating user:", error);
    throw error;
  }
}

/**
 * Delete a user document
 *
 * @param id - The document ID of the user
 *
 * @example
 * await deleteUser("abc123");
 */
export async function deleteUser(id: string): Promise<void> {
  try {
    const docRef = doc(db, "users", id);
    await deleteDoc(docRef);
  } catch (error) {
    console.error("Error deleting user:", error);
    throw error;
  }
}
