
#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import logging
import os
import re

import webapp2
import jinja2

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import mail
from google.appengine.api import users

#load jinja2 templates from template folder
template_dir = os.path.join(os.path.dirname(__file__),'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),autoescape=True)

#helper function
def render_str(template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

#blog post database
class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_now_add = True)


    def render(self):
        self._render_text = self.content.replace('\n','<br>')
        return render_str("post.html", p = self)


class Handler(webapp2.RequestHandler):
    def write(self, *a,**kw):
        self.response.out.write(*a,**kw)

    def render_str(self, template, **params):
    	t = jinja_env.get_template(template)
    	return t.render(params)

    def render(self,template,**kw):
        self.write(self.render_str(template,**kw))


class HomePage(Handler):
    def get(self): 
        posts = top_posts()
        state = posts[0].key().parent().name()
        self.render('home.html',state=state)

class NewPost(Handler):
    def get(self):
        #google users api authentication
        user = users.get_current_user()

        if user and users.is_current_user_admin():  #confirm administrator                
                #no markup, so adding these code snippets to easily add photos/videos from phone.   
                code="""Img Code:

                    <a href="?dl=1"><img src="dl=1" alt=""></a>

                    Vimeo Code:

                    <div class="embed-container"><iframe src="" frameborder="0" webkitAllowFullScreen mozallowfullscreen allowFullScreen></iframe></div>

                    Youtube Code:

                    <div class="embed-container"><iframe src="" frameborder="0" allowfullscreen></iframe></div> """       
                self.render('newpost.html',code=code,user=user.nickname(),url=users.create_logout_url("/"))
                      
        else:
            user = ("<a class='btn' href=\"%s\">Sign in</a>" %
                        users.create_login_url("/newpost"))
            self.render('login.html', user=user)
            #self.write("<html><body>%s</body></html>" % user)

    def post(self):
        subject = self.request.get('subject')
        content = self.request.get('content')
        state = self.request.get('state')

        if subject and content:    
            new_post = Post(subject=subject,content=content,parent=state_key(state)) #creates a new database object
            new_post.put() #stores object
            get_posts(state,True) # update state page filter
            top_posts(True) #update front page of blog
            post_id = str(new_post.key().id()) #finds db ojbect's key                   
            self.redirect('/%s/%s' % (state,post_id)) #redirects to permalink page  

 
class PermaLink(Handler):  
    def get(self,state,post_id):
        post = memcache.get(state + post_id)
        if post is None:
            post = Post.get_by_id(int(post_id),parent=state_key(state))
            logging.error("DB QUERY FOR PERMALINK")
            memcache.set(state + post_id,post)
        self.render("permalink.html",post=post)


class StatePage(Handler):
    def get(self,state):
        ##posts = db.GqlQuery("select * from Post where ancestor is :1 order by created desc",state_key(state))  
        posts = get_posts(state)   
        count = len(posts)
        self.render('sblog.html',posts=posts,state=state, count=count)

 
def state_key(group = 'default'):  
#lookup ancestor key; used to pull all state posts
    return db.Key.from_path('Post', group) 


class EditView(Handler):
    def get(self):
        posts = db.GqlQuery("select * from Post order by created desc")  
        self.render("edit.html", posts=posts)

class EditPost(Handler):
    def get(self,state,post_id):
        user = users.get_current_user()
        if user and users.is_current_user_admin():
            post = Post.get_by_id(int(post_id),parent=state_key(state))
            code="""Img Code:

                        <a href="?dl=1"><img src="dl=1" alt=""></a>

                        Vimeo Code:

                        <div class="embed-container"><iframe src="" frameborder="0" webkitAllowFullScreen mozallowfullscreen allowFullScreen></iframe></div>

                        Youtube Code:

                        <div class="embed-container"><iframe src="" frameborder="0" allowfullscreen></iframe></div> """   
            self.render("editpost.html",subject=post.subject,content=post.content,state=state,code=code,
                        user=user.nickname(),url=users.create_logout_url("/"))
        else:
            user = ("<a class='btn' href=\"%s\">Sign in</a>" %
                        users.create_login_url("/%s/%s/edit" % (state,post_id)))
            self.render('login.html', user=user)

    def post(self,state,post_id):
        post = Post.get_by_id(int(post_id),parent=state_key(state))
        post.subject = self.request.get('subject')
        post.content = self.request.get('content')
        post.state = self.request.get('state')
        post.put()
    
        memcache.set(state + post_id,post) #update permalink with edits.
        get_posts(state,True) #update filtered states with edits
        top_posts(True)
        self.redirect('/%s/%s' % (state,post_id))

class About(Handler):
    def get(self):
        self.render('about.html')

class Gear(Handler):
    def get(self):
        self.render('gear.html')

class FAQs(Handler):
    def get(self):        
        self.render('FAQ.html')

class Links(Handler):
    def get(self):
        self.render('links.html')

def top_posts(update=False):
    posts = memcache.get('top')
    if posts is None or update:
        posts = db.GqlQuery("select * from Post order by created desc limit 10")
        logging.error("DB Query hit")
        posts = list(posts)
        memcache.set('top',posts)
    return posts


def get_posts(state, update=False):
    posts = memcache.get(state)
    if posts is None or update:
        posts = db.GqlQuery("select * from Post where ancestor is :1 order by created desc",state_key(state))
        logging.error("DB Query")
        posts = list(posts)
        memcache.set(state,posts)
    return posts

NAME_RE = re.compile(r"^[ a-zA-Z_-]{2,30}$")
def valid_name(username):
    return username and NAME_RE.match(username)

EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)

class Contact(Handler):
    def get(self):
        self.render('contact.html')

    def post(self):
        author= self.request.get('author')
        email = self.request.get('email')
        message = self.request.get('content')

        if valid_name(author) and valid_email(email) and message:  
            contact = mail.EmailMessage()
            contact.sender = 'jxberc@gmail.com'
            contact.reply_to = '%s <%s>' % (author,email)
            logging.error(contact.reply_to)
            contact.to = 'jxberc@gmail.com'
            contact.subject = "New AT Jindo Message from: %s" % author
            contact.body = message 
            contact.send()                 
            self.redirect('/thanks?n=%s' % author ) #redirects to permalink page  
        else:
            self.render('contact.html', error="*Sorry, your message did not send. Please enter valid and required fields.")

class Support(Handler):
    def get(self):
        self.render('help.html')

class Thanks(Handler):
    def get(self):
        name = self.request.get('n')
        self.render('thanks.html', name=name)

app = webapp2.WSGIApplication([
    ('/', HomePage),
    ('/newpost', NewPost),
    ('/edit', EditView),
    ('/links',Links),
    ('/(ME|NH|VT|MA|CT|NY|NJ|PA|MD|WV|VA|NC|TN|GA|XX)/(\d+)/edit', EditPost),
    ('/(ME|NH|VT|MA|CT|NY|NJ|PA|MD|WV|VA|NC|TN|GA|XX)/(\d+)', PermaLink),
    ('/(ME|NH|VT|MA|CT|NY|NJ|PA|MD|WV|VA|NC|TN|GA|XX)', StatePage),   
    ('/about',About),  
    ('/gear',Gear),
    ('/FAQs',FAQs),
    ('/support',Support),
    ('/contact',Contact),
    ('/thanks',Thanks)

], debug=True)
