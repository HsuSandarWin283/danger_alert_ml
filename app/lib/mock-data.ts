import { SearchResult, GroupMember } from './trusted-group-types'

export const mockUsers: SearchResult[] = [
  {
    uid: 'user-1',
    name: 'Alice Johnson',
    email: 'alice@example.com',
    photoURL: 'https://ui-avatars.com/api/?name=Alice+Johnson&background=random',
    isMember: false,
  },
  {
    uid: 'user-2',
    name: 'Bob Smith',
    email: 'bob@example.com',
    photoURL: 'https://ui-avatars.com/api/?name=Bob+Smith&background=random',
    isMember: false,
  },
  {
    uid: 'user-3',
    name: 'Carol Williams',
    email: 'carol@example.com',
    photoURL: 'https://ui-avatars.com/api/?name=Carol+Williams&background=random',
    isMember: true,
  },
  {
    uid: 'user-4',
    name: 'David Brown',
    email: 'david@example.com',
    photoURL: 'https://ui-avatars.com/api/?name=David+Brown&background=random',
    isMember: false,
  },
]

export const mockGroupMembers: GroupMember[] = [
  {
    groupId: 'default-trusted-group',
    userId: 'user-3',
    joinedAt: new Date('2024-01-15'),
  },
  {
    groupId: 'default-trusted-group',
    userId: 'user-5',
    joinedAt: new Date('2024-02-20'),
  },
]

export const mockGroups = [
  {
    groupId: 'default-trusted-group',
    groupName: 'My Trusted Contacts',
    ownerId: 'current-user',
  },
]