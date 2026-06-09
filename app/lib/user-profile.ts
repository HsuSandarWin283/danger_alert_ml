import { db } from './firebase'
import { doc, setDoc, getDoc } from 'firebase/firestore'
import { User } from './trusted-group-types'

const USERS_COLLECTION = 'users'

export async function createUserProfile(uid: string, name: string, email: string, photoURL?: string): Promise<void> {
  await setDoc(doc(db, USERS_COLLECTION, uid), {
    uid,
    name,
    email,
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