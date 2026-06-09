import { db } from './firebase'
import {
  collection,
  query,
  where,
  getDocs,
  getDoc,
  addDoc,
  deleteDoc,
  doc,
  serverTimestamp,
  onSnapshot,
} from 'firebase/firestore'
import { User, GroupMember, SearchResult } from './trusted-group-types'

const USERS_COLLECTION = 'users'
const GROUP_MEMBERS_COLLECTION = 'group_members'

export function searchUsers(searchQuery: string, currentUserId: string, callback: (results: SearchResult[]) => void) {
  return onSnapshot(query(collection(db, USERS_COLLECTION)), async (snapshot) => {
    const allUsers: User[] = snapshot.docs.map((doc) => ({
      uid: doc.id,
      ...doc.data(),
    })) as User[]

    const filtered = allUsers.filter(
      (user) =>
        user.uid !== currentUserId &&
        (user.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          user.email?.toLowerCase().includes(searchQuery.toLowerCase()))
    )

    const userIds = filtered.map((u) => u.uid)
    const memberUserIds = new Set<string>()

    if (userIds.length > 0) {
      const membersSnapshot = await getDocs(
        query(collection(db, GROUP_MEMBERS_COLLECTION), where('userId', 'in', userIds))
      )
      membersSnapshot.docs.forEach((d) => memberUserIds.add(d.data().userId))
    }

    const results: SearchResult[] = filtered.map((user) => ({
      ...user,
      isMember: memberUserIds.has(user.uid),
    }))

    callback(results)
  })
}

export async function searchUsersOnce(searchQuery: string, currentUserId: string): Promise<SearchResult[]> {
  const snapshot = await getDocs(collection(db, USERS_COLLECTION))
  const allUsers: User[] = snapshot.docs.map((doc) => ({
    uid: doc.id,
    ...doc.data(),
  })) as User[]

  const filtered = allUsers.filter(
    (user) =>
      user.uid !== currentUserId &&
      (user.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        user.email?.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  const userIds = filtered.map((u) => u.uid).slice(0, 10)
  const memberUserIds = new Set<string>()

  if (userIds.length > 0) {
    const membersSnapshot = await getDocs(
      query(collection(db, GROUP_MEMBERS_COLLECTION), where('userId', 'in', userIds))
    )
    membersSnapshot.docs.forEach((d) => memberUserIds.add(d.data().userId))
  }

  return filtered.map((user) => ({
    ...user,
    isMember: memberUserIds.has(user.uid),
  }))
}

export async function addMemberToGroup(groupId: string, userId: string): Promise<void> {
  await addDoc(collection(db, GROUP_MEMBERS_COLLECTION), {
    groupId,
    userId,
    joinedAt: serverTimestamp(),
  })
}

export async function removeMemberFromGroup(groupId: string, userId: string): Promise<void> {
  const q = query(
    collection(db, GROUP_MEMBERS_COLLECTION),
    where('groupId', '==', groupId),
    where('userId', '==', userId)
  )
  const snapshot = await getDocs(q)
  if (!snapshot.empty) {
    await deleteDoc(doc(db, GROUP_MEMBERS_COLLECTION, snapshot.docs[0].id))
  }
}

export function getGroupMembers(groupId: string, callback: (members: GroupMember[]) => void) {
  return onSnapshot(
    query(collection(db, GROUP_MEMBERS_COLLECTION), where('groupId', '==', groupId)),
    (snapshot) => {
      const members = snapshot.docs.map((doc) => ({
        ...doc.data(),
        joinedAt: doc.data().joinedAt?.toDate() || new Date(),
      })) as GroupMember[]
      callback(members)
    }
  )
}

export async function getUserById(userId: string): Promise<User | null> {
  const { getUserProfile } = await import('./user-profile')
  return getUserProfile(userId)
}