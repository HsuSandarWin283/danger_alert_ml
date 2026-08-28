'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/app/auth-provider';
import { useRouter } from 'next/navigation';
import { getHelpHistoryForUser, type HelpMessage } from '@/app/lib/help-history';
import { getUserProfile, type User } from '@/app/lib/user-profile';
import Navbar from '@/app/components/Navbar';
import { useLang } from '@/app/lib/LanguageProvider';

type HelpItemWithUser = HelpMessage & { senderUser?: User | null };

export default function HelpHistoryPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { t } = useLang();
  const [items, setItems] = useState<HelpItemWithUser[]>([]);
  const [loading, setLoading] = useState(true);

  const formatDangerType = (type: string | null | undefined): string | null => {
    if (!type) return null
    const lower = type.toLowerCase()
    if (lower === 'gunshot' || lower === 'accident') {
      return t('dangerousSound')
    }
    if (lower === 'scream') {
      return t('screamSound')
    }
    if (lower === 'trouble') {
    return t('trouble');
  }
    return type.toUpperCase()
  }

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      try {
        const data = await getHelpHistoryForUser(user.uid);
        if (!cancelled) {
          const senderIds = Array.from(new Set(data.map((item) => item.senderId)));
          const senderProfiles = await Promise.all(
            senderIds.map((uid) => getUserProfile(uid).catch(() => null)),
          );
          const profileMap = new Map<string, User | null>();
          senderIds.forEach((uid, idx) => {
            profileMap.set(uid, senderProfiles[idx]);
          });
          const enriched = data.map((item) => ({
            ...item,
            senderUser: profileMap.get(item.senderId) ?? null,
          }));
          setItems(enriched);
        }
      } catch (err) {
        console.error('[HelpHistoryPage] Failed to load help history', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const openMap = (lat: number, lng: number, name?: string) => {
    const q = name || `${lat},${lng}`;
    const url = `https://maps.google.com/maps?q=${encodeURIComponent(q)}`;
    window.open(url, '_blank');
  };

  const callPhone = (phone: string) => {
    window.location.href = `tel:${encodeURIComponent(phone)}`;
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-600" suppressHydrationWarning>{t('loadingHelpHistory')}</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="min-h-screen bg-gray-100">
      <Navbar
        userEmail={user.email}
        showBack
        onBack={() => router.push('/settings')}
        onLogout={() => {}}
      />

      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-3xl font-bold text-gray-800 mb-2">{t('helpHistoryTitle')}</h2>
        <p className="text-gray-600 mb-6">{t('helpHistoryDesc')}</p>

        {items.length === 0 ? (
          <div className="bg-white rounded-3xl shadow-lg p-10 text-center">
            <p className="text-gray-500">{t('noHelpAlerts')}</p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => {
              const isSender = item.senderId === user.uid;
              const senderName = item.senderUser?.name || item.senderName || <span> ( {t('deletedUser')} ) </span>;
              const isDeletedUser = !item.senderUser?.name;
              const isDangerCard = !!item.dangerType;
              return (
                <div key={item.id} className="bg-white rounded-3xl shadow-lg p-6">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900">
                        {item.dangerType
                          ? `${t('danger')}: ${formatDangerType(item.dangerType)}`
                          : t('helpRequest')}
                      </h3>
                      <p className="text-sm text-gray-500">
                        {item.createdAt ? new Date(item.createdAt).toLocaleString() : ''}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        {isSender
                          ? `To: ${item.receiverIds?.length ?? 0} ${t('members')}`
                          : `From: ${senderName}`}
                      </p>
                    </div>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-semibold uppercase ${
                        isSender ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                      }`}
                    >
                      {isSender ? t('sent') : t('received')}
                    </span>
                  </div>
                  {isDangerCard ? (
                    <div className="mt-3 space-y-1">
                     <p className={`text-sm ${isDeletedUser ? 'text-red-600' : 'text-gray-700'}`}>
                        {senderName} {t('needsHelp')}
                        {isDeletedUser &&   <span> ( {t('deletedUser')} ) </span>}
                      </p>
                      <div>
                      {!isSender && (item.senderUser?.phone) && (
                        <button
                          onClick={() => callPhone(item.senderUser?.phone!!)}
                          className="text-sm text-blue-600 underline mt-1"
                        >
                          {item.senderUser?.phone}
                        </button>
                      )}
                      </div>
                      {item.lat !== undefined && item.lng !== undefined && (
                        <button
                          onClick={() => openMap(item.lat!, item.lng!, item.locationName)}
                          className="text-sm text-blue-600 underline mt-2"
                        >
                          {t('location')}:{' '}
                          {item.locationName || `${item.lat.toFixed(4)}, ${item.lng.toFixed(4)}`}
                        </button>
                      )}
                    </div>
                  ) : (
                    <>
                      <p className="text-gray-700 whitespace-pre-line">{item.alertMsg}</p>
                      {item.lat !== undefined && item.lng !== undefined && (
                        <button
                          onClick={() => openMap(item.lat!, item.lng!, item.locationName)}
                          className="text-sm text-blue-600 underline mt-2"
                        >
                          {t('location')}:{' '}
                          {item.locationName || `${item.lat.toFixed(4)}, ${item.lng.toFixed(4)}`}
                        </button>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
