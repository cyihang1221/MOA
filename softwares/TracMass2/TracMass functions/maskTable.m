function [t] = maskTable(tab,mask);
%[t] = maskTable(tab,mask);
% keeps those rows for which mask is true.

%by: Magnus Åberg
fn = fieldnames(tab);

for i = 1:numel(fn)
   if size(tab.(fn{i}),1)==numel(mask)
      t.(fn{i}) = tab.(fn{i})(mask,:);
   else
      t.(fn{i}) = tab.(fn{i});
   end
end