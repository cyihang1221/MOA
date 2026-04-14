function ChildrenVisibility(handle,change)
%Erik Tengstrand
set(handle,'Visible',change)
c=get(handle,'Children');
for N=1:numel(c)
    set(c(N),'Visible',change)
end
