export interface User {
  uid: string
  name: string
  email: string
  photoURL?: string
}

export interface Group {
  groupId: string
  groupName: string
  ownerId: string
}

export interface GroupMember {
  groupId: string
  userId: string
  joinedAt: Date
}

export interface SearchResult extends User {
  isMember: boolean
}