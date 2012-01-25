#!/usr/bin/python

# A class for getting contact information from vodafone.ie's SMS number contact
# list, and exporting them as a vodasms config friendly format.
# (See mackers' http://o2sms.sourceforge.net/)
#
# The easiest way to fetch this list is logging into the vodafone.ie webmail
# section, which can export the contact numbers as a csv file.
# Whenever we detect the session is expired, try re-login once and continue.


import cookielib
import urllib
import urllib2
import urlparse
import re


class VodafoneIEMail:
    def __init__(self, username, password, DEBUG=False):
        self.username = username
        self.password = password
        self.cookies = cookielib.CookieJar()
        self.t = ''
        if DEBUG:
            self.opener = urllib2.build_opener(
                    urllib2.HTTPCookieProcessor(self.cookies), urllib2.HTTPHandler(debuglevel=1), urllib2.HTTPSHandler(debuglevel=1))
        else:
            self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookies))
        self.opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
        self.login()
        self.mail_login()
        return

    def _fetchurl(self, url, post=None, fetch_html=True):
        """Helper function to request url, get html and cleanup connection."""
        request = urllib2.Request(url, post)
        response = self.opener.open(request)
        if fetch_html:
            html = response.read()
            response.close()
            return html, response
        else:
            response.close()
            return None, response

    def login(self):
        # Login to the vodafone.ie website to collect the session cookies (JSESSIONID and others)
        self.cookies.clear()
        self.t = ''
        # Acquire a JSESSIONID cookie
        self._fetchurl('https://vodafone.ie', fetch_html=False)

        # Do the actual login, and check we can access the vodafone mail page.
        url = 'https://vodafone.ie/myv/services/login/Login.shtml'
        post = urllib.urlencode({'username': self.username, 'password': self.password, 'redirect': '/myv/messaging/vodafonemail/index.jsp'})
        html, resp = self._fetchurl(url, post)
        if 'https://vodafone.ie/myv/messaging/vodafonemail/index.jsp' != resp.geturl():
            errmsg = re.search('module-alert">.+?(<h2>.+?)</div>', html, re.DOTALL)
            if errmsg:
                raise Exception('Unable to login: \n' + errmsg.group(1))
            else:
                raise Exception('Unable to login: Unknown error (try re-running with DEBUG=True)')
        return

    def mail_login(self):
        # Return cookies and the '?t=xxxx' session ID needed to use the Vodafone Webmail service.
        # This function is used by the others to authenticate

        # Try to reuse existing login first (from stored cookies)
        # Open the Vodafone Mail link, to get more session IDs and cookies for later use
        url = 'https://vodafone.ie/myv/messaging/vodafonemail/Launch.shtml'
        html, resp = self._fetchurl(url)
        if 'Your session has expired' in html or 'webmail1.vodafone.ie' not in resp.geturl():
            self.login()
            _, resp = self._fetchurl(url, fetch_html=False)
        queries = urlparse.parse_qs(urlparse.urlparse(resp.geturl()).query)
        if 'webmail1.vodafone.ie' not in resp.geturl() or 't' not in queries:
            raise Exception('Unable to access Vodafone Webmail (try re-running with DEBUG=True)')
        self.t = queries['t'][0]
        return

    def add_contact(self, new_name, new_number):
        # Add a contact to Vodafone Mail contacts list, which also
        # appears in the webtext contact list

        # It seems necessary to request the New Contact page before submitting
        # the post request, or else we get back a 500 Internal Server Error
        newcon_url = 'http://webmail1.vodafone.ie:8080/cp/ps/PSPab/new_contact?d=vodafone.ie&u=unusedaddress&st=NewContact1&t=' + self.t
        newcon_html, newcon_resp = self._fetchurl(newcon_url)
        if 'Your session has expired' in newcon_html:
            self.mail_login()
            self._fetchurl(newcon_url, fetch_html=False)

        # Upload the contact information with a post request
        con_url = 'http://webmail1.vodafone.ie:8080/cp/ps/PSPab/AddContact?d=vodafone.ie&u=unusedaddress&t=' + self.t
        con_post = urllib.urlencode({'firstName': new_name, 'homeMobile': new_number})
        con_html, _ = self._fetchurl(con_url, con_post)
        # Note: The 'Contact has been added.' string is commented out 
        # in the html reply from vodafone so it might not be there forever...
        if 'Contact has been added.' in con_html:
            print "['" + new_name + "': '" + new_number + "' has been added to the contact list]"
        else:
            print 'Error adding new contact, (try re-running with DEBUG=True)'
            raise Exception
        return

    def get_contacts_rawcsv(self):
        # Return the CSV file of Names and phone numbers of the contacts
        # associated with the vodafone.ie account given.

        # Use the session IDs and cookies to download the CSV file
        url = 'http://webmail1.vodafone.ie:8080/cp/ps/PSPab/Downloader?d=vodafone.ie&c=yes&u=unusedaddress&dhid=contactsDownloader&t=' + self.t
        post = urllib.urlencode({'exportbook': 'PAB://vodafone.ie/unusedaddress/main', 'fileFormat': 'CSV', 'charset': '8859_1', 'Button': 'Export Contacts'})
        csv, _ = self._fetchurl(url, post)
        return csv

    def get_contacts(self):
        dat = self.get_contacts_rawcsv()
        lines = [[x.strip('"') for x in l.split(',')] for l in dat.splitlines()]
        nameidx = lines[0].index('First Name')
        numidx = lines[0].index('Home Phone 2')
        return [(l[nameidx], l[numidx]) for l in lines[1:]]

    def read_contact_pages(self):
        pass    # Unimplemented
        # need to parse the results out of the page
        # using the IDs in this list, we can delete contacts

    def logout(self):
        mail_logout_url = 'http://webmail1.vodafone.ie:8080/cp/ps/Main/logout/Logout?d=vodafone.ie&u=unusedaddress&t=' + self.t
        self._fetchurl(mail_logout_url, fetch_html=False)
        vodafone_logout_url = 'https://vodafone.ie/myv/services/logout/Logout.shtml'
        self._fetchurl(vodafone_logout_url, fetch_html=False)
        self.t = ''

    def __del__(self):
        self.logout()



if __name__ == '__main__':
    import os
    config = open(os.path.expanduser('~/.vodasms/config')).read()
    username = re.search('^username (.+?)$', config, re.MULTILINE).group(1)
    password = re.search('^password (.+?)$', config, re.MULTILINE).group(1)
    #vfmail = VodafoneIEMail(username, password, DEBUG=True)
    vfmail = VodafoneIEMail(username, password)
    for contact in vfmail.get_contacts():
        print 'alias',
        # vodasms doesn't support spaces in names, so replace with underscores.
        print contact[0].replace(' ', '_'),
        print contact[1]

    #vfmail.add_contact('Test User', '1234')
