# -*- coding: utf-8 -*-
from django.db import models, utils
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.contrib.comments import Comment
from django.db.models import Max

import norduni_client as nc

NODE_META_TYPE_CHOICES = (
    ('logical', 'Logical'),
    ('physical', 'Physical'),
    ('relation', 'Relation'),
    ('location', 'Location'),
)

class UserProfile(models.Model):
    user = models.OneToOneField(User)

def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

post_save.connect(create_user_profile, sender=User)

class NodeType(models.Model):
    type = models.CharField(unique=True, max_length=255)
    slug = models.SlugField(unique=True, help_text='Suggested value \
        #automatically generated from type. Must be unique.')

    def __unicode__(self):
        return self.type

    def get_slug(self):
        return self.slug

    @models.permalink
    def get_absolute_url(self):
        return('niweb.apps.noclook.views.list_by_type', (), {
            'slug': self.slug})
            
    def delete(self):
        """
        Delete the NodeType object with all associated NodeHandles.
        """
        for nh in NodeHandle.objects.filter(node_type=self.pk):
            nh.delete() 
        super(NodeType, self).delete()
        return True
    delete.alters_data = True

class NodeHandle(models.Model):
    # Handle <-> Node data
    handle_id = models.AutoField(primary_key=True)
    node_id = models.BigIntegerField(null=True, blank=True, unique=True,
        editable=False)
    # Data shared with the node
    node_name = models.CharField(max_length=200)
    node_type = models.ForeignKey(NodeType)
    node_meta_type = models.CharField(max_length=255,
        choices=NODE_META_TYPE_CHOICES)
    # Meta information
    creator = models.ForeignKey(User, related_name='creator')
    created = models.DateTimeField(auto_now_add=True)
    modifier = models.ForeignKey(User, null=True, blank=True, related_name='modifier')
    modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '%s %s' % (self.node_type, self.node_name)
        
    def get_node(self):
        """
        Returns the NodeHandles node.
        """
        return nc.get_node_by_id(nc.neo4jdb, self.node_id)
    
    def delete_node_id(self, create_node=True):
        """
        Sets the node_id property to None to be able to create a new node for 
        the NodeHandle in a later stage. If create_node is True a new node is
        generated in the save call.
        """
        self.node_id = None
        self.save(create_node=create_node, force_update=True)
        return self

    @models.permalink
    def get_absolute_url(self):
        """
        Should we instead import neo4jclient here and traverse the node
        to to root? That way we can do urls like se-tug/fpc/pic/port or
        dk-ore-lm-01/rack/sub_rack/.
        """
        #return '%s/%d/' % (self.node_type, self.handle_id)
        return('niweb.apps.noclook.views.generic_detail', (), {
            'slug': self.node_type.get_slug(),
            'handle_id': self.handle_id})

    def save(self, create_node=False, *args, **kwargs):
        """
        Create a new node and associate it to the handle.
        """
        if self.node_id and not create_node: # Don't create a node
            super(NodeHandle, self).save(*args, **kwargs)
            return self
        node = nc.create_node(nc.neo4jdb, self.node_name, str(self.node_type))
        self.node_id = node.id
        try:
            super(NodeHandle, self).save(*args, **kwargs)
        except utils.IntegrityError as e:
            print e
            print 'Node ID: %d' % node.id
            raise Exception(e)
        meta_node = nc.get_meta_node(nc.neo4jdb, str(self.node_meta_type))
        node = nc.get_node_by_id(nc.neo4jdb, self.node_id)
        with nc.neo4jdb.transaction:
            node['handle_id'] = int(self.handle_id)
            meta_node.Contains(node)
        return self
    
    save.alters_data = True

    def delete(self):
        """
        Delete that node handle and the handles node.
        """
        try:
            node = self.get_node()
            nc.delete_node(nc.neo4jdb, node)
        except KeyError:
            # Node already deleted
            pass
        Comment.objects.filter(object_pk=self.pk).delete()
        super(NodeHandle, self).delete()
        return True
        
    delete.alters_data = True


class UniqueId(models.Model):
    """
    Model that provides a base id counter, prefix, suffix and id length. When a new
    id is generated the base id counter will increase by 1.
    """
    name = models.CharField(max_length=256, unique=True)
    base_id = models.IntegerField(default=1)
    zfill = models.BooleanField()
    base_id_length = models.IntegerField(default=0,
                                         help_text="Base id will be filled with leading zeros to this length if zfill is checked.")
    prefix = models.CharField(max_length=256, null=True, blank=True)
    suffix = models.CharField(max_length=256, null=True, blank=True)
    last_id = models.CharField(max_length=256, editable=False)
    next_id = models.CharField(max_length=256, editable=False)
    # Meta
    creator = models.ForeignKey(User, related_name='unique_id_creator')
    created = models.DateTimeField(auto_now_add=True)
    modifier = models.ForeignKey(User, null=True, blank=True, related_name='unique_id_modifier')
    modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.name

    def get_id(self):
        """
        Returns the next id and increments the base_id field.
        """
        base_id = self.base_id
        if self.zfill:
            base_id = str(self.base_id).zfill(self.base_id_length)
        unique_id = '%s%s%s' % (self.prefix, base_id, self.suffix)
        self.last_id = unique_id
        self.base_id += 1
        self.save()
        return unique_id

    def save(self, *args, **kwargs):
        """
        Increments the base_id.
        """
        base_id = self.base_id
        if self.zfill:
            base_id = str(self.base_id).zfill(self.base_id_length)
        self.next_id = '%s%s%s' % (self.prefix, base_id, self.suffix)
        super(UniqueId, self).save(*args, **kwargs)

    save.alters_data = True


class FreeRangeManager(models.Manager):
    """
    A manager that helps finding free ranged of NORDUnet IDs to reserve.
    """
    def find_range(self, min_base_id, max_base_id, quantity):
        """
        Recursively tries to find an unused range of quantity ids between min and max
        base id.
        """
        for i in range(min_base_id, max_base_id):
            self.get()

    def reserve_range(self, min_base_id, quantity):
        """
        Reserves and returns a list of previous unused ids for the specified quantity.
        """
        max_base_id = self.aggregate(Max('base_id'))
        range = self.find_range(min_base_id, max_base_id, quantity)
        # TODO
        # Create IDs and set reserved = True
        # Return list of IDs


class NORDUnetIdSet(models.Model):
    """
    Table for ensuring that NORDUnet IDs are unique.
    """
    nordunet_id = models.CharField(max_length=256, unique=True)
    reserved = models.BooleanField()
    base_id = models.IntegerField(null=True, blank=True)
    objects = FreeRangeManager()
    # Meta
    creator = models.ForeignKey(User, related_name='nordunet_id_creator')
    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        try:
            self.base_id = int(self.nordunet_id.replace('NU-', ''))
        except ValueError:
            self.base_id = None
        super(NORDUnetIdSet, self).save(*args, **kwargs)

    save.alters_data = True