import { db } from './firebase'
import { doc, setDoc, getDoc, onSnapshot } from 'firebase/firestore'
import type { User } from './trusted-group-types'

const USERS_COLLECTION = 'users'

export async function createUserProfile(uid: string, name: string, email: string, phone?: string, photoURL?: string): Promise<void> {
  await setDoc(doc(db, USERS_COLLECTION, uid), {
    uid,
    name,
    email,
    phone: phone || null,
    photoURL: photoURL || null,
  }, { merge: true })
}

export async function getUserProfile(uid: string): Promise<User | null> {
  const docSnap = await getDoc(doc(db, USERS_COLLECTION, uid))
  if (docSnap.exists()) {
    return { uid: docSnap.id, ...docSnap.data() } as User
  }
  return null
}

export function subscribeToUser(uid: string, callback: (user: User | null) => void): () => void {
  return onSnapshot(doc(db, USERS_COLLECTION, uid), (snap) => {
    if (snap.exists()) {
      callback({ uid: snap.id, ...snap.data() } as User)
    } else {
      callback(null)
    }
  })
}

export { User }
