package com.danger.alert;

import android.content.Context;
import android.content.SharedPreferences;

public class NotificationStrings {
    private final String lang;

    public NotificationStrings(Context context) {
        SharedPreferences prefs = context.getSharedPreferences("capacitor", Context.MODE_PRIVATE);
        this.lang = prefs.getString("app_lang", "en");
    }

    private boolean isMy() {
        return "my".equals(lang);
    }

    public String channelMonitoringName() {
        return isMy() ? "အန္တရာယ်ရှိသည့်အသံ စောင့်ကြည့်ရေး" : "Danger Sound Monitoring";
    }

    public String channelMonitoringDesc() {
        return isMy() ? "အန္တရာယ်ရှိသည့်အသံ စောင့်ကြည့်ခြင်း ဖွင့်ထားချိန်တွင် ပြသခြင်း" : "Shows when danger sound monitoring is active";
    }

    public String channelAlertsName() {
        return isMy() ? "အန္တရာယ်သတိပေးချက်များ" : "Danger Alerts";
    }

    public String channelAlertsDesc() {
        return isMy() ? "အရေးပေါ်အန္တရာယ်ရှိသည့်အသံ သတိပေးချက်များ" : "Critical danger sound alerts";
    }

    public String notificationTitle() {
        return isMy() ? "အန္တရာယ်သတိပေးချက်" : "Danger Alert";
    }

    public String monitoringForDangerSounds() {
        return isMy() ? "အန္တရာယ်ရှိသည့်အသံများအတွက် စောင့်ကြည့်နေသည်..." : "Monitoring for danger sounds...";
    }

    public String listeningForDangerSounds() {
        return isMy() ? "အန္တရာယ်ရှိသည့်အသံများ နားထောင်နေသည်..." : "Listening for danger sounds...";
    }

    public String micPermissionDenied() {
        return isMy() ? "မိုက်ခရိုဖုန်းခွင့်ပြုချက်ငြင်းဆိုထားသည်" : "Microphone permission denied";
    }

    public String audioUnavailable() {
        return isMy() ? "အသံဖမ်းယူခြင်း မရနိုင်ပါ" : "Audio recording unavailable";
    }

    public String stop() {
        return isMy() ? "ရပ်ရန်" : "Stop";
    }

    public String dangerDetectedTitle(String type) {
        if (isMy()) {
            return "အန္တရာယ်: " + type.toUpperCase() + " ရှာဖွေတွေ့ရှိပါပြီ!";
        }
        return "DANGER: " + type.toUpperCase() + " detected!";
    }

    public String areYouOk() {
        return isMy() ? "သင် ဘေးကင်းပါသလား?" : "Are you OK?";
    }

    public String dangerDetectedScreenTitle() {
        return isMy() ? "အန္တရာယ်ရှာဖွေတွေ့ရှိပါပြီ!" : "Danger Detected!";
    }

    public String dangerFoundMessage(String type) {
        if (isMy()) {
            return "သင့်အနီးတွင် " + type.toUpperCase() + " အသံ ရှာဖွေတွေ့ရှိပါသည်။\nသင် ဘေးကင်းပါသလား?";
        }
        return "I found " + type.toUpperCase() + " sound near you.\nAre you OK?";
    }

    public String dangerTypeTitle(String type) {
        if (isMy()) {
            return "အန္တရာယ်: " + type.toUpperCase();
        }
        return "Danger : " + type.toUpperCase();
    }

    public String dangerSoundFoundNear() {
        if (isMy()) {
            return "သင့်အနားနားတွင် အန္တရာယ်ရှိသည့်အသံတွေ့ရှိပါပြီ";
        }
        return "Danger Sound found near around you?";
    }

    public String autoSendHelp(long mins, long secs) {
        if (isMy()) {
            return String.format("အလိုအလျောက်ပေးပို့မည် %02d:%02d", mins, secs);
        }
        return String.format("Auto send in %d:%02d", mins, secs);
    }

    public String autoSendingHelp() {
        return isMy() ? "အလိုအလျောက်ပေးပို့နေသည်..." : "Auto sending help...";
    }

    public String imOk() {
        return isMy() ? "ကျွန်တော်/ကျွန်မ ဘေးကင်းပါတယ်" : "I'm OK";
    }

    public String imNotOkSendHelp() {
        return isMy() ? "ကျွန်တော်/ကျွန်မ ဘေးမကင်ပါ - အကူအညီပို့ပါ" : "I'm NOT OK - Send Help";
    }

    public String sendingHelpRequest() {
        return isMy() ? "အကူအညီတောင်းချက် ပို့နေသည်..." : "Sending help request...";
    }

    public String pushSentTo(int count) {
        if (isMy()) {
            return "Push notification " + count + " ဦးထံ ပို့ဆောင်ပြီးပါပြီ!";
        }
        return "Push notification sent to " + count + " member!";
    }

    public String foundMembersNoTokens(int count) {
        if (isMy()) {
            return "အဖွဲ့ဝင် " + count + " ဦး ရှာဖွေတွေ့ရှိသော်လည်း FCM token မရှိသေးပါ။\nအဖွဲ့ဝင်သည် app ကိုဖွင့်ပြီး စောင့်ကြည့်ခြင်း စတင်ပေးပါ။";
        }
        return "Found " + count + " member(s) but they don't have FCM tokens yet.\nMember needs to open the app and start monitoring first.";
    }

    public String foundMembersPushFailed(int count) {
        if (isMy()) {
            return "အဖွဲ့ဝင် " + count + " ဦး ရှာဖွေတွေ့ရှိသော်လည်း push ပို့ခြင်းမအောင်မြင်ပါ။\nအဖွဲ့ဝင် app/ကွန်ရက်/service account ခွင့်ပြုချက်များကို စစ်ဆေးပါ။";
        }
        return "Found " + count + " member(s) but push failed.\nCheck member app/network/service account permissions.";
    }

    public String noTrustedMembers() {
        return isMy()
                ? "ယုံကြည်ရသူ အဖွဲ့ဝင် မတွေ့ပါ။\nTrusted Group ဆက်တင်ထဲတွင် အဖွဲ့ဝင်ထည့်ပါ။"
                : "No trusted group members found.\nAdd members in Trusted Group settings.";
    }

    public String pushTitle(String dangerType) {
        return "DANGER: " + dangerType.toUpperCase();
    }

    public String needsHelp() {
        return isMy() ? "အကူအညီလိုအပ်နေသည်" : "needs help";
    }

    public String needsHelpWithName(String name) {
        return isMy() ? name + " အကူအညီလိုအပ်နေသည်" : name + " needs help";
    }

    public String locationLabel() {
        return isMy() ? "တည်နေရာ" : "Location";
    }

    public String close() {
        return isMy() ? "ပိတ်ရန်" : "Close";
    }

    public String locationUnavailable(String reason) {
        return isMy() ? "တည်နေရာ မရနိုင်ပါ (" + reason + ")" : "Location unavailable (" + reason + ")";
    }

    public String locationUnavailableDefault() {
        return isMy() ? "တည်နေရာ မရနိုင်ပါ" : "Location unavailable";
    }

    public String failed(String reason) {
        return isMy() ? "မအောင်မြင်ပါ: " + reason : "Failed: " + reason;
    }

    public String helpAlertDefaultTitle() {
        return isMy() ? "အကူအညီတောင်းခံချက်" : "Help Request";
    }

    public String helpAlertDefaultBody() {
        return isMy() ? "တစ်စုံတစ်ယောက် အကူအညီလိုအပ်နေသည်!" : "Someone needs your help!";
    }

    public String helpAlertTitle(String senderName) {
        if (isMy()) {
            return senderName + " အကူအညီလိုအပ်နေသည်!";
        }
        return senderName + " needs help!";
    }

    public String modelOfflineTitle() {
        return isMy() ? "မော်ဒယ်အော့ဖ်လိုင်း" : "AI Model Offline";
    }

    public String modelOfflineMessage() {
        return isMy() ? "မော်ဒယ်စ server အော့ဖ်လိုင်းဖြစ်နေပါသည်။ စောင့်ကြည့်ခြင်း မအောင်မြင်နိုင်ပါ။" : "AI Model server is offline. Monitoring may not work.";
    }
}
