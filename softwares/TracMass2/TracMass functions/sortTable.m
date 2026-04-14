function tabs = sortTable(tab,col,direction)
%tabs = sortTable(tab,col,direction)
%
% Sorts the columns of struct table tab in ascending order on named column
% col (a string), direction = 'ascend' | 'descend'

%by: Magnus Åberg

dir = 'ascend';
if nargin>2,
   dir = direction;
end

fn = fieldnames(tab);

if ~any(strcmp(col,fn))
   error(['sortTable: column ', col, ' does not exist']);
end

[tmp,I] = sort(tab.(col),dir);
N = numel(I);

for i = 1:numel(fn)
   if size(tab.(fn{i}),1)==N;
      tabs.(fn{i}) = tab.(fn{i})(I);
   else
      tabs.(fn{i}) = tab.(fn{i});
   end
end
  

