import { db } from './firebase'
import {
  collection,
  query,
  where,
  getDocs,
  addDoc,
  serverTimestamp,
  orderBy,
  onSnapshot,
} from 'firebase/firestore'
import { User } from './trusted-group-types'

export interface HelpMessage {
  id?: string
  senderId: string
  senderName: string
  senderPhone?: string
  receiverIds: string[]
  dangerType: string
  alertMsg: string
  lat?: number
  lng?: number
  locationName?: string
  createdAt?: Date
}

const HELP_COLLECTION = 'help_history'

export async function saveHelpMessage(msg: Omit<HelpMessage, 'id' | 'createdAt'>): Promise<void> {
  const payload: Record<string, unknown> = {
    senderId: msg.senderId,
    senderName: msg.senderName,
    receiverIds: msg.receiverIds,
    dangerType: msg.dangerType,
    alertMsg: msg.alertMsg,
  }
  if (msg.senderPhone) payload.senderPhone = msg.senderPhone
  if (typeof msg.lat === 'number') payload.lat = msg.lat
  if (typeof msg.lng === 'number') payload.lng = msg.lng
  if (msg.locationName) payload.locationName = msg.locationName
  payload.createdAt = serverTimestamp()
  await addDoc(collection(db, HELP_COLLECTION), payload)
}

function toHelpMessage(d: any): HelpMessage {
  const data = d.data() as HelpMessage
  return {
    id: d.id,
    ...data,
    createdAt: ((data.createdAt as any)?.toDate?.() || new Date()) as Date,
  }
}

export async function getHelpHistoryForUser(userId: string): Promise<HelpMessage[]> {
  const sent = query(collection(db, HELP_COLLECTION), where('senderId', '==', userId))
  const received = query(collection(db, HELP_COLLECTION), where('receiverIds', 'array-contains', userId))
  const [sentSnap, receivedSnap] = await Promise.all([getDocs(sent), getDocs(received)])
  const results = [
    ...sentSnap.docs.map(toHelpMessage),
    ...receivedSnap.docs.map(toHelpMessage),
  ]
  console.log('[HelpHistory] userId=', userId, 'sent=', sentSnap.size, 'received=', receivedSnap.size, 'total=', results.length)
  const seen = new Set<string>()
  const unique = results.filter((item) => {
    if (!item.id) return true
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
  unique.sort((a, b) => {
    const aTime = a.createdAt?.getTime() || 0
    const bTime = b.createdAt?.getTime() || 0
    return bTime - aTime
  })
  return unique
}

export function listenHelpHistory(userId: string, callback: (items: HelpMessage[]) => void) {
  const sent = query(collection(db, HELP_COLLECTION), where('senderId', '==', userId))
  const received = query(collection(db, HELP_COLLECTION), where('receiverIds', 'array-contains', userId))
  const unsubSent = onSnapshot(sent, (snapshot) => {
    const items = snapshot.docs.map(toHelpMessage)
    callback(items)
  })
  const unsubReceived = onSnapshot(received, (snapshot) => {
    const items = snapshot.docs.map(toHelpMessage)
    callback(items)
  })
  return () => {
    unsubSent()
    unsubReceived()
  }
}
