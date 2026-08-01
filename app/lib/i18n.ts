export type Lang = 'en' | 'my'

export const translations: Record<Lang, Record<string, string>> = {
  en: {
    // Navbar
    back: 'Back',
    helpHistory: 'Help History',
    profile: 'Profile',
    logout: 'Logout',
    logoutConfirm: 'Are you sure you want to logout?',
    emergencySOS: 'Emergency SOS',

    // Hero
    heroTitle: 'AI-Powered Personal Safety',
    heroDesc: 'Real-time danger sound detection using CNN, Mel-Spectrograms, and emergency alert systems.',
    startMonitoring: 'Start Monitoring',
    stopListening: 'Stop Listening',
    monitoring: 'Monitoring...',
    trustedGroup: 'Trusted Group',

    // StatusCard
    systemStatus: 'System Status',
    microphone: 'Microphone',
    aiModel: 'AI Model',
    environment: 'Environment',
    active: 'Active',
    inactive: 'Inactive',
    running: 'Running',
    checking: 'Checking...',
    offline: 'Offline',
    monitoringLabel: 'Monitoring',

    // DangerAlert
    dangerDetection: 'Danger Detection',
    detectedSound: 'Detected Sound',
    confidence: 'Confidence',
    waitingForDetection: 'Waiting for detection...',
    sendEmergencyAlert: 'Send Emergency Alert',
    sending: 'Sending...',
    sendSuccess: 'Send success',
    sendFailed: 'send failed',

    // MicrophoneMonitor
    micMonitorTitle: 'Microphone Monitor',
    status: 'Status',
    rmsLevel: 'RMS Level',
    lastPrediction: 'Last Prediction',
    none: 'None',
    startMonitoringBtn: 'Start Monitoring',
    stopMonitoringBtn: 'Stop Monitoring',
    permission: 'Permission',

    // AudioVisualizer
    liveSpectrogram: 'Live Audio Spectrogram',

    // Footer
    copyright: '© 2026 AI Personal Safety Companion',

    // Login
    loginTitle: 'Log In',
    loginDesc: 'Log in to your account to access your safety dashboard.',
    email: 'Email',
    password: 'Password',
    loggingIn: 'Logging in...',
    logIn: 'Log In',
    noAccount: "Don't have an account?",
    signUp: 'Sign Up',
    loginFailed: 'Login failed. Please try again.',

    // Signup
    signupTitle: 'Sign Up',
    signupDesc: 'Create an account to get started.',
    name: 'Name',
    phoneNumber: 'Phone Number',
    creatingAccount: 'Creating account...',
    haveAccount: 'Already have an account?',
    signupFailed: 'Signup failed. Please try again.',

    // Profile
    editProfile: 'Edit Profile',
    updateProfileDesc: 'Update your personal information',
    phone: 'Phone',
    photoURL: 'Photo URL',
    saving: 'Saving...',
    saveProfile: 'Save Profile',
    profileUpdated: 'Profile updated',
    profileUpdateFailed: 'Failed to update profile',
    loading: 'Loading...',

    // Help History
    helpHistoryTitle: 'Help History',
    helpHistoryDesc: 'Alerts sent by you or received from your trusted group',
    noHelpAlerts: 'No help alerts yet.',
    helpRequest: 'Help Request',
    sent: 'Sent',
    received: 'Received',
    location: 'Location',
    loadingHelpHistory: 'Loading help history...',
    danger: 'Danger',
    members: 'member(s)',

    // Trusted Group
    trustedGroupTitle: 'Trusted Group Management',
    trustedGroupDesc: 'Manage your trusted contacts for emergency alerts',
    searchAndAddUsers: 'Search & Add Users',
    searchUsers: 'Search users...',
    searchingUsers: 'Searching users...',
    noUsersFound: 'No users found matching your search',
    startTyping: 'Start typing to search for users',
    currentGroupMembers: 'Current Group Members',
    noMembersYet: 'No members in your trusted group yet',
    unnamedUser: 'Unnamed User',
    added: 'Added',
    adding: 'Adding...',
    add: 'Add',
    joined: 'Joined',
    removing: 'Removing...',
    remove: 'Remove',
    backToDashboard: 'Back to Dashboard',
    loadingTrustedGroup: 'Loading trusted group...',

    // Settings
    settings: 'Settings',
    language: 'Language',

    // Mic Monitor page
    micMonitorPageTitle: 'Microphone Monitor | AI Safety Companion',
    micMonitorPageDesc: 'Monitor microphone for danger detection',
  },
  my: {
    // Navbar
    back: 'နောက်သို့',
    helpHistory: 'အကူအညီ မှတ်တမ်း',
    profile: 'ပရိုဖိုင်',
    logout: 'ထွက်ရန်',
    logoutConfirm: 'သင် ထွက်လိုက်မည်လား?',
    emergencySOS: 'အရေးပေါ် SOS',

    // Hero
    heroTitle: 'AI ဖြင့် အသုံးပြုသည့် ကိုယ်ရေးလုံခြုံရေး',
    heroDesc: 'CNN, Mel-Spectrograms နှင့် အရေးပေါ်သတိပေးစနစ်များ အသုံးပြု၍ အန္တရာယ်ရှိသည့်အသံများကို အချိန်နှင့်တပြေးညီ ရှာဖွေဖော်ပြခြင်း။',
    startMonitoring: 'စတင်စောင့်ကြည့်ရန်',
    stopListening: 'နားထောင်ခြင်းရပ်ရန်',
    monitoring: 'စောင့်ကြည့်နေသည်...',
    trustedGroup: 'ယုံကြည်ရသူများအုပ်စု',

    // StatusCard
    systemStatus: 'စနစ်အခြေအနေ',
    microphone: 'မိုက်ခရိုဖုန်း',
    aiModel: 'AI မော်ဒယ်',
    environment: 'ပတ်ဝန်းကျင်',
    active: 'ဖွင့်ထားသည်',
    inactive: 'ပိတ်ထားသည်',
    running: 'အလုပ်လုပ်နေသည်',
    checking: 'စစ်ဆေးနေသည်...',
    offline: 'အွန်လိုင်းမဟုတ်',
    monitoringLabel: 'စောင့်ကြည့်နေသည်',

    // DangerAlert
    dangerDetection: 'အန္တရာယ်ရှာဖွေခြင်း',
    detectedSound: 'ရှာဖွေတွေ့ရှိသည့်အသံ',
    confidence: 'ယုံကြည်မှုရာခိုင်နှုန်း',
    waitingForDetection: 'ရှာဖွေခြင်းအတွက် စောင့်ဆိုင်းနေသည်...',
    sendEmergencyAlert: 'အရေးပေါ်သတိပေးချက်ပို့ရန်',
    sending: 'ပို့နေသည်...',
    sendSuccess: 'ပို့ဆောင်ပြီးပါပြီ',
    sendFailed: 'ပို့ဆောင်ခြင်းမအောင်မြင်ပါ',

    // MicrophoneMonitor
    micMonitorTitle: 'မိုက်ခရိုဖုန်း စောင့်ကြည့်ရေး',
    status: 'အခြေအနေ',
    rmsLevel: 'RMS အဆင့်',
    lastPrediction: 'နောက်ဆုံးခန့်မှန်းချက်',
    none: 'မရှိ',
    startMonitoringBtn: 'စတင်စောင့်ကြည့်ရန်',
    stopMonitoringBtn: 'စောင့်ကြည့်ခြင်းရပ်ရန်',
    permission: 'ခွင့်ပြုချက်',

    // AudioVisualizer
    liveSpectrogram: 'တိုက်ရိုက်အသံ spectrogram',

    // Footer
    copyright: '© 2026 AI ကိုယ်ရေးလုံခြုံရေး Companion',

    // Login
    loginTitle: 'ဝင်ရန်',
    loginDesc: 'သင့်အကောင့်သို့ ဝင်ရောက်ပါ။',
    email: 'အီးမေးလ်',
    password: 'စကားဝှက်',
    loggingIn: 'ဝင်နေသည်...',
    logIn: 'ဝင်ရန်',
    noAccount: 'အကောင့်မရှိသေးပါလား?',
    signUp: 'စာရင်းသွင်းရန်',
    loginFailed: 'ဝင်ခြင်းမအောင်မြင်ပါ။ ထပ်ကြိုးစားပါ။',

    // Signup
    signupTitle: 'စာရင်းသွင်းရန်',
    signupDesc: 'အကောင့်တစ်ခုဖန်တီးပါ။',
    name: 'အမည်',
    phoneNumber: 'ဖုန်းနံပါတ်',
    creatingAccount: 'အကောင့်ဖန်တီးနေသည်...',
    haveAccount: 'အကောင့်ရှိပြီးသားလား?',
    signupFailed: 'စာရင်းသွင်းခြင်းမအောင်မြင်ပါ။ ထပ်ကြိုးစားပါ။',

    // Profile
    editProfile: 'ပရိုဖိုင်ပြင်ဆင်ရန်',
    updateProfileDesc: 'သင့်ကိုယ်ရေးအချက်အလက်များ ပြင်ဆင်ပါ',
    phone: 'ဖုန်း',
    photoURL: 'ဓာတ်ပုံ URL',
    saving: 'သိမ်းဆည်းနေသည်...',
    saveProfile: 'ပရိုဖိုင်သိမ်းရန်',
    profileUpdated: 'ပရိုဖိုင်ပြင်ဆင်ပြီးပါပြီ',
    profileUpdateFailed: 'ပရိုဖိုင်ပြင်ဆင်ခြင်းမအောင်မြင်ပါ',
    loading: 'ဖွင့်နေသည်...',

    // Help History
    helpHistoryTitle: 'အကူအညီ မှတ်တမ်း',
    helpHistoryDesc: 'သင်ပို့ဆောင်ခဲ့သည့် သို့မဟုတ် ယုံကြည်ရသူများအုပ်စုမှ လက်ခံရရှိသည့် သတိပေးချက်များ',
    noHelpAlerts: 'အကူအညီသတိပေးချက် မရှိသေးပါ။',
    helpRequest: 'အကူအညီတောင်းချက်',
    sent: 'ပို့ပြီး',
    received: 'လက်ခံရရှိပြီး',
    location: 'တည်နေရာ',
    loadingHelpHistory: 'အကူအညီမှတ်တမ်းဖွင့်နေသည်...',
    danger: 'အန္တရာယ်',
    members: 'အဖွဲ့ဝင်',

    // Trusted Group
    trustedGroupTitle: 'ယုံကြည်ရသူများအုပ်စု စီမံခြင်း',
    trustedGroupDesc: 'အရေးပေါ်သတိပေးချက်များအတွက် ယုံကြည်ရသူများကို စီမံပါ',
    searchAndAddUsers: 'အသုံးပြုသူများ ရှာဖွေပြီးထည့်ရန်',
    searchUsers: 'အသုံးပြုသူများ ရှာဖွေရန်...',
    searchingUsers: 'အသုံးပြုသူများ ရှာဖွေနေသည်...',
    noUsersFound: 'သင့်ရှာဖွေမှုနှင့် ကိုက်ညီသည့် အသုံးပြုသူ မတွေ့ပါ',
    startTyping: 'အသုံးပြုသူများ ရှာဖွေရန် ရိုက်ထည့်ပါ',
    currentGroupMembers: 'လက်ရှိအုပ်စုအဖွဲ့ဝင်များ',
    noMembersYet: 'ယုံကြည်ရသူများအုပ်စုတွင် အဖွဲ့ဝင် မရှိသေးပါ',
    unnamedUser: 'အမည်မသိအသုံးပြုသူ',
    added: 'ထည့်ပြီး',
    adding: 'ထည့်နေသည်...',
    add: 'ထည့်ရန်',
    joined: 'ဝင်ပြီး',
    removing: 'ဖယ်ရှားနေသည်...',
    remove: 'ဖယ်ရှားရန်',
    backToDashboard: 'ဒက်ရှ်ဘုတ်သို့ ပြန်ရန်',
    loadingTrustedGroup: 'ယုံကြည်ရသူများအုပ်စု ဖွင့်နေသည်...',

    // Settings
    settings: 'ဆက်တင်',
    language: 'ဘာသာစကား',

    // Mic Monitor page
    micMonitorPageTitle: 'မိုက်ခရိုဖုန်း စောင့်ကြည့်ရေး | AI ကိုယ်ရေးလုံခြုံရေး Companion',
    micMonitorPageDesc: 'အန္တရာယ်ရှာဖွေခြင်းအတွက် မိုက်ခရိုဖုန်းကို စောင့်ကြည့်ပါ',
  },
}

export type TranslationKey = keyof typeof translations.en
