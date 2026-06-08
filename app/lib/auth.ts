import { auth } from '@/app/lib/firebase'
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  User,
} from 'firebase/auth'

export async function loginWithEmail(email: string, password: string) {
  if (!auth) {
    throw new Error('Firebase auth is not configured.')
  }
  const credential = await signInWithEmailAndPassword(auth, email, password)
  return credential.user
}

export async function signupWithEmail(email: string, password: string) {
  if (!auth) {
    throw new Error('Firebase auth is not configured.')
  }
  const credential = await createUserWithEmailAndPassword(auth, email, password)
  return credential.user
}

export async function logout() {
  if (!auth) {
    return
  }
  await firebaseSignOut(auth)
}

export function listenToAuth(callback: (user: User | null) => void) {
  if (!auth) {
    callback(null)
    return () => {}
  }
  return onAuthStateChanged(auth, callback)
}
